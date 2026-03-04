"""Ingestion cycle orchestrator — composes leaf modules into a working pipeline."""

import asyncio
import calendar
import uuid
from datetime import datetime, timezone

import httpx
import structlog
from sqlalchemy import delete, select, update

from factfeed.config import settings
from factfeed.db.models import Article, Sentence, Source, Translation
from factfeed.ingestion.deduplicator import compute_url_hash
from factfeed.ingestion.extractor import extract_article, parse_article_date
from factfeed.ingestion.fetcher import can_fetch, fetch_article_page, fetch_rss_feed
from factfeed.services.system_monitor import monitor

log = structlog.get_logger()

# Per-source consecutive failure counters
_failure_counts: dict[str, int] = {}


async def run_ingestion_cycle(session_factory, http_client: httpx.AsyncClient) -> dict:
    """Run one complete ingestion cycle across all sources.

    Fetches all RSS feeds concurrently, then processes article pages
    sequentially per source with a politeness delay.
    """
    monitor.start_cycle()
    cycle_id = str(uuid.uuid4())[:8]

    async with session_factory() as session:
        result = await session.execute(select(Source))
        sources = result.scalars().all()

    source_count = len(sources)
    log.info("ingestion_cycle_start", cycle_id=cycle_id, source_count=source_count)

    # Build source dicts for the fetcher
    source_dicts = [
        {"name": s.name, "feed_url": s.feed_url, "id": s.id, "language": s.language}
        for s in sources
    ]

    monitor.set_task(f"Fetching RSS feeds from {source_count} sources")

    # Fetch all feeds concurrently
    feed_results = await asyncio.gather(
        *[fetch_rss_feed(sd, http_client) for sd in source_dicts],
        return_exceptions=True,
    )

    monitor.set_task("Processing source feeds concurrently")

    # Process all sources concurrently
    processing_tasks = []
    for source_dict, feed_result in zip(source_dicts, feed_results):
        processing_tasks.append(
            _process_feed_safe(source_dict, feed_result, http_client, session_factory)
        )

    results = await asyncio.gather(*processing_tasks)

    aggregate = {
        "total_found": sum(r["found"] for r in results),
        "total_inserted": sum(r["inserted"] for r in results),
        "total_skipped": sum(r["skipped"] for r in results),
        "total_errors": sum(r["errors"] for r in results),
    }

    monitor.end_cycle()
    log.info("ingestion_cycle_end", cycle_id=cycle_id, **aggregate)
    return aggregate


async def _process_feed_safe(
    source_dict: dict, feed_result, http_client, session_factory
) -> dict:
    """Safely process a feed result, handling errors and stats aggregation."""
    source_name = source_dict["name"]
    stats = {"found": 0, "inserted": 0, "skipped": 0, "errors": 0}

    if isinstance(feed_result, Exception):
        _log_source_error(source_name, str(feed_result))
        stats["errors"] += 1
        return stats

    # Note: monitor updates here are race-prone but acceptable for rough stats
    monitor.add_queued(len(feed_result.entries))

    try:
        source_stats = await _process_source_entries(
            source_dict, feed_result, http_client, session_factory
        )
        _reset_failure_count(source_name)
        stats.update(source_stats)
    except Exception as exc:
        _log_source_error(source_name, str(exc))
        stats["errors"] += 1

    return stats


async def _process_source_entries(
    source: dict, feed, http_client: httpx.AsyncClient, session_factory
) -> dict:
    """Process all entries from a single source's RSS feed."""
    source_name = source["name"]
    source_id = source["id"]
    language = source.get("language")
    stats = {"found": len(feed.entries), "inserted": 0, "skipped": 0, "errors": 0}

    for entry in feed.entries:
        try:
            url = entry.get("link", "")
            if not url:
                stats["errors"] += 1
                monitor.add_failed()
                continue

            url_hash = compute_url_hash(url)

            # Check for duplicates or partial articles to retry
            is_update = False
            try:
                async with session_factory() as session:
                    stmt = select(Article.is_partial).where(
                        Article.url_hash == url_hash
                    )
                    result = await session.execute(stmt)
                    existing_partial = result.scalar_one_or_none()

                    if existing_partial is False:
                        # Full article exists, skip
                        stats["skipped"] += 1
                        monitor.add_skipped()
                        log.debug(
                            "article_duplicate_skipped", source=source_name, url=url
                        )
                        continue
                    elif existing_partial is True:
                        # Partial article exists, retry fetch
                        is_update = True
                        log.info(
                            "retrying_partial_article", source=source_name, url=url
                        )
            except Exception as exc:
                log.warning(
                    "duplicate_check_failed",
                    source=source_name,
                    url=url,
                    error=str(exc),
                )
                stats["errors"] += 1
                monitor.add_failed()
                continue

            # Check robots.txt
            if not await can_fetch(url, settings.user_agent, http_client):
                stats["skipped"] += 1
                monitor.add_skipped()
                log.debug("article_robots_blocked", source=source_name, url=url)
                continue

            # Fetch article page
            html_bytes = await fetch_article_page(url, http_client)

            # Extract content
            rss_summary = entry.get("summary", "")
            if html_bytes is not None:
                extracted = extract_article(html_bytes, url, rss_summary)
            else:
                # No HTML fetched — use partial fallback from RSS summary
                extracted = {
                    "body": rss_summary or "",
                    "body_html": f"<p>{rss_summary or ''}</p>",
                    "author": None,
                    "published_at": None,
                    "lead_image_url": None,
                    "is_partial": True,
                }

            # Parse published date: feedparser's published_parsed > extractor date > now
            published_at = _resolve_published_date(entry, extracted)

            # Build article data dict
            article_data = {
                "url": url,
                "url_hash": url_hash,
                "title": entry.get("title", "Untitled"),
                "body": extracted["body"],
                "body_html": extracted["body_html"],
                "author": extracted["author"],
                "published_at": published_at,
                "lead_image_url": extracted["lead_image_url"],
                "is_partial": extracted["is_partial"],
                "source_id": source_id,
                "language": language,
            }

            # Persist
            try:
                async with session_factory() as session:
                    if is_update:
                        # Update existing partial article
                        stmt = (
                            update(Article)
                            .where(Article.url_hash == url_hash)
                            .values(
                                title=article_data["title"],
                                body=article_data["body"],
                                body_html=article_data["body_html"],
                                author=article_data["author"],
                                lead_image_url=article_data["lead_image_url"],
                                published_at=article_data["published_at"],
                                is_partial=article_data["is_partial"],
                                language=article_data["language"],
                            )
                        )
                        await session.execute(stmt)

                        # Delete existing sentences so the full text is reclassified
                        del_stmt = delete(Sentence).where(
                            Sentence.article_id
                            == select(Article.id)
                            .where(Article.url_hash == url_hash)
                            .scalar_subquery()
                        )
                        await session.execute(del_stmt)

                        # Invalidate translation cache to prevent stale content
                        del_trans = delete(Translation).where(
                            Translation.article_id
                            == select(Article.id)
                            .where(Article.url_hash == url_hash)
                            .scalar_subquery()
                        )
                        await session.execute(del_trans)

                        await session.commit()
                        stats["inserted"] += 1
                        monitor.add_processed()

                        if article_data["is_partial"]:
                            log.warning(
                                "retry_still_partial", source=source_name, url=url
                            )
                        else:
                            log.info(
                                "retry_success_full_content",
                                source=source_name,
                                url=url,
                            )
                    else:
                        from factfeed.ingestion.persister import save_article

                        inserted = await save_article(session, article_data)
                        if inserted:
                            stats["inserted"] += 1
                            monitor.add_processed()
                        else:
                            stats["skipped"] += 1
                            monitor.add_skipped()
            except Exception as exc:
                log.warning(
                    "article_save_failed", source=source_name, url=url, error=str(exc)
                )
                stats["errors"] += 1
                monitor.add_failed()

            # Politeness delay between article fetches
            await asyncio.sleep(settings.article_fetch_delay)

        except Exception as exc:
            log.error(
                "unhandled_entry_error",
                source=source_name,
                error=str(exc),
                entry_link=entry.get("link"),
            )
            stats["errors"] += 1
            monitor.add_failed()

    log.info("source_complete", source=source_name, **stats)
    return stats


def _resolve_published_date(entry, extracted: dict) -> datetime:
    """Resolve the best available published date for an article."""
    # 1. feedparser's published_parsed (struct_time)
    published_parsed = entry.get("published_parsed")
    if published_parsed is not None:
        try:
            return datetime.fromtimestamp(
                calendar.timegm(published_parsed), tz=timezone.utc
            )
        except (ValueError, OverflowError, OSError):
            pass

    # 2. Extractor's date string
    extracted_date = extracted.get("published_at")
    if extracted_date:
        parsed = parse_article_date(extracted_date)
        if parsed is not None:
            return parsed

    # 3. Fallback to now
    return datetime.now(timezone.utc)


def _log_source_error(source_name: str, error: str) -> None:
    """Log a source-level error and track consecutive failures."""
    _failure_counts[source_name] = _failure_counts.get(source_name, 0) + 1
    count = _failure_counts[source_name]

    if count >= settings.consecutive_failure_threshold:
        log.error(
            "source_consecutive_failures",
            source=source_name,
            error=error,
            consecutive_failures=count,
        )
    else:
        log.warning(
            "source_fetch_error",
            source=source_name,
            error=error,
            consecutive_failures=count,
        )


def _reset_failure_count(source_name: str) -> None:
    """Reset the consecutive failure counter for a source."""
    _failure_counts[source_name] = 0
