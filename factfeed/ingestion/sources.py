"""Source definitions for all five target RSS feeds."""

# Each source is stored in the database via seed_sources() on startup.
# The feed_url values here are the initial seeds; they can be updated in the
# database without a code change.

SOURCES = [
    {"name": "BBC News", "feed_url": "http://feeds.bbci.co.uk/news/rss.xml"},
    # NOTE: Reuters' RSS feed URL has historically been unstable.  Using the
    # sitemap-based feed as a fallback; the URL is stored in the sources DB
    # table so it can be updated without code changes.
    {
        "name": "Reuters",
        "feed_url": "https://www.reuters.com/arc/outboundfeeds/news-sitemap-index/?outputType=xml",
    },
    # NOTE: AP News has no obvious stable first-party RSS feed.  Using the
    # RSSHub proxy as recommended by research.
    {"name": "AP News", "feed_url": "https://rsshub.app/apnews/topics/apf-topnews"},
    {"name": "NPR", "feed_url": "https://feeds.npr.org/1001/rss.xml"},
    {"name": "Al Jazeera", "feed_url": "https://www.aljazeera.com/xml/rss/all.xml"},
]
