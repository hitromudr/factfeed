import re

import pytest
from playwright.sync_api import Page, expect

# Assumes app is running on host networking on port 8002 as per docker-compose configuration
BASE_URL = "http://localhost:8002"


def test_home_page_structure(page: Page):
    """Verify essential search page elements are present and localization works."""
    page.goto(BASE_URL)

    # Verify title contains app name (English "The Sorter" or Russian "Сортировочная")
    expect(page).to_have_title(
        re.compile(r"The Sorter|Сортировочная|FactFeed"), timeout=30000
    )

    # Verify search input and filters exist
    expect(page.locator("input[name='q']")).to_be_visible(timeout=30000)
    expect(page.locator("select[name='source']")).to_be_visible(timeout=30000)
    expect(page.locator("select[name='from']")).to_be_visible(timeout=30000)


def test_search_results_exist(page: Page):
    """
    Ensure that the ingestion pipeline has populated the list.
    Fails if the database is empty.
    """
    page.goto(BASE_URL)

    # Wait for article cards. Fail if "No articles" persists for too long.
    try:
        expect(page.locator(".article-card").first).to_be_visible(timeout=30000)
    except AssertionError:
        # Check if we have the empty state
        if page.locator(".no-results").is_visible():
            pytest.fail(
                "Database is empty. Ensure 'make reset' finished and ingestion is running."
            )
        raise


def test_inline_expansion_http_status(page: Page):
    """
    CRITICAL TEST: Verifies that clicking an article title triggers
    a correct GET request to /article/{id}/inline and receives a 200 OK.

    This specifically guards against the regression where relative paths caused 404s
    (e.g., requesting 'inline?lang=ru' relative to current URL instead of absolute path).
    """
    page.goto(BASE_URL)

    # Get the first article card
    card = page.locator(".article-card").first
    expect(card).to_be_visible(timeout=30000)

    # Parse ID from DOM id="card-{id}" to verify URL correctness later
    card_id = card.get_attribute("id")
    assert card_id and card_id.startswith("card-")
    article_id = card_id.split("-")[1]

    # Define regex for the expected API call
    # We want to ensure it calls /article/X/inline
    target_url_regex = re.compile(rf"/article/{article_id}/inline")

    # Wait for the specific response triggered by the click
    with page.expect_response(target_url_regex) as response_info:
        # Click the title to trigger expansion
        card.locator("h2.article-title a").click()

    response = response_info.value

    # 1. Verify Status
    assert response.status == 200, (
        f"Expected 200 OK, got {response.status} from {response.url}"
    )

    # 2. Verify URL Structure (Absolute path check)
    assert f"/article/{article_id}/inline" in response.url, (
        f"Malformed request URL: {response.url}"
    )

    # 3. Verify Content-Type (should be HTML partial)
    assert "text/html" in response.headers.get("content-type", "")

    # 4. Verify UI State
    inline_container = page.locator(f"#inline-{article_id}")
    expect(inline_container).to_be_visible(timeout=30000)

    # Verify expand/collapse controls are loaded inside the partial
    expect(inline_container.locator("button[title*='Collapse']")).to_be_visible(
        timeout=30000
    )


def test_inline_collapse_interaction(page: Page):
    """Verify that the user can collapse the article after reading using both top and bottom buttons."""
    page.goto(BASE_URL)
    card = page.locator(".article-card").first
    expect(card).to_be_visible(timeout=30000)
    card_id = card.get_attribute("id")
    article_id = card_id.split("-")[1]
    inline_container = page.locator(f"#inline-{article_id}")

    # 1. Expand
    card.locator("h2.article-title a").click()
    expect(inline_container).to_be_visible(timeout=30000)

    # 2. Click Collapse (Top button - usually icon)
    # Filter by functionality since text might be translated
    collapse_btn_top = inline_container.locator(".inline-controls.top button").first
    collapse_btn_top.click()

    # Should be hidden
    expect(inline_container).not_to_be_visible(timeout=30000)

    # 3. Expand again
    card.locator("h2.article-title a").click()
    expect(inline_container).to_be_visible(timeout=30000)

    # 4. Click Close (Bottom button - usually large button)
    close_btn_bottom = inline_container.locator(".inline-controls.bottom button").first
    close_btn_bottom.click()

    expect(inline_container).not_to_be_visible(timeout=30000)
