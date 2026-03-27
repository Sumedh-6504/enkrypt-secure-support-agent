import asyncio
import httpx
from bs4 import BeautifulSoup
import markdownify


async def fetch_and_parse(url: str, client: httpx.AsyncClient) -> dict:
    """Fetches a single URL, strips noise, and converts to Markdown."""
    try:
        # 1. Fetch the page asynchronously
        response = await client.get(url, timeout=10.0)
        response.raise_for_status()  # Raise exception for 404, 500, etc.

        # 2. Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')

        # 3. DESTROY THE NOISE (Crucial for AI/RAG!)
        # We remove navigation, footers, scripts, and styles so the LLM only reads the docs.
        for element in soup(["nav", "footer", "script", "style", "header", "aside", "svg"]):
            element.decompose()

        # 4. Target the main content area
        # Doc sites usually keep the good stuff in <main>, <article>, or an element with role="main"
        main_content = soup.find('main') or soup.find('article') or soup.find(role='main') or soup.find('body')

        # 5. Convert clean HTML to LLM-friendly Markdown
        markdown_text = markdownify.markdownify(str(main_content), heading_style="ATX").strip()

        # Clean up excessive blank lines
        clean_markdown = "\n".join([line for line in markdown_text.splitlines() if line.strip()])

        return {
            "url": url,
            "content": clean_markdown,
            "status": "success"
        }

    except Exception as e:
        return {
            "url": url,
            "content": str(e),
            "status": "error"
        }


async def scrape_docs_concurrently(urls: list[str]) -> list[dict]:
    """Scrapes a list of URLs concurrently for maximum speed."""
    # We use a single client session for connection pooling
    async with httpx.AsyncClient(follow_redirects=True) as client:
        # Create a list of concurrent tasks
        tasks = [fetch_and_parse(url, client) for url in urls]

        # Execute all tasks simultaneously
        results = await asyncio.gather(*tasks)
        return results


# --- HOW TO RUN IT FOR REAL ---
# scraper.py
async def run_scraper(target_urls: list[str] = None):
    """Callable async entrypoint to trigger the scraper from an API."""
    if target_urls is None:
        target_urls = [
            "https://docs.enkryptai.com/home/introduction",
            "https://docs.enkryptai.com/get-started/introduction",
            "https://docs.enkryptai.com/api-reference/introduction",
            "https://docs.enkryptai.com/sdk-reference/python/introduction",
            "https://docs.enkryptai.com/schema-and-postman/introduction",
            "https://docs.enkryptai.com/resources/introduction"
        ]

    print(f"🚀 Background Task: Scraping {len(target_urls)} pages...")
    scraped_data = await scrape_docs_concurrently(target_urls)

    # Save to the root Modal directory where your agent expects it
    doc_path = "/root/enkrypt_docs.txt"
    with open(doc_path, "w", encoding="utf-8") as f:
        for page in scraped_data:
            if page["status"] == "success":
                f.write(f"\n\n### SOURCE: {page['url']} ###\n\n")
                f.write(page["content"])

    print("Background Scraping complete! Data saved to disk.")
    return True
