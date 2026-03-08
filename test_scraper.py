import pytest
from scraper import scrape_docs_concurrently

# Tell pytest we are running async tests
pytestmark = pytest.mark.asyncio


async def test_successful_markdown_extraction():
    """TEST 1: Ensure the scraper fetches a page and returns clean Markdown."""
    # We use a reliable, fast-loading URL for the test
    urls = ["https://docs.enkrypt.ai/"]  # Or any specific Enkrypt doc page

    results = await scrape_docs_concurrently(urls)

    assert len(results) == 1
    assert results[0]["status"] == "success"
    assert results[0]["url"] == urls[0]
    # Ensure it converted to markdown (looking for headers or basic text)
    assert len(results[0]["content"]) > 50


async def test_noise_removal():
    """TEST 2: Ensure HTML fluff (scripts, styles) is stripped out."""
    urls = ["https://example.com"]

    results = await scrape_docs_concurrently(urls)
    content = results[0]["content"].lower()

    # These tags should NOT exist in our clean LLM context
    assert "<script>" not in content
    assert "<style>" not in content
    assert "<html>" not in content


async def test_graceful_error_handling():
    """TEST 3: Ensure a 404/Bad URL doesn't crash the pipeline."""
    urls = ["https://docs.enkrypt.ai/this-page-definitely-does-not-exist-12345"]

    results = await scrape_docs_concurrently(urls)

    assert len(results) == 1
    assert results[0]["status"] == "error"
    # It should return the URL so we know which one failed
    assert results[0]["url"] == urls[0]