import asyncio
import httpx
from bs4 import BeautifulSoup
import markdownify
import os
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.ingestion.database import DatabaseManager
from src.orchestration.vector_management import VectorStoreFactory

async def fetch_and_parse(url: str, client: httpx.AsyncClient) -> dict:
    """Fetches a single URL, strips noise, and converts to Markdown."""
    try:
        response = await client.get(url, timeout=10.0)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        for element in soup(["nav", "footer", "script", "style", "header", "aside", "svg"]):
            element.decompose()

        main_content = soup.find('main') or soup.find('article') or soup.find(role='main') or soup.find('body')
        markdown_text = markdownify.markdownify(str(main_content), heading_style="ATX").strip()
        clean_markdown = "\n".join([line for line in markdown_text.splitlines() if line.strip()])

        return {
            "url": url,
            "content": clean_markdown,
            "status": "success"
        }
    except Exception as e:
        return {"url": url, "content": str(e), "status": "error"}

async def scrape_docs_concurrently(urls: list[str]) -> list[dict]:
    async with httpx.AsyncClient(follow_redirects=True) as client:
        tasks = [fetch_and_parse(url, client) for url in urls]
        results = await asyncio.gather(*tasks)
        return results

async def run_scraper(target_urls: list[str] = None):
    db = DatabaseManager()
    vs_factory = VectorStoreFactory()
    vectorstore = vs_factory.get_vector_store()
    
    if target_urls is None:
        target_urls = [
            "https://docs.enkryptai.com/home/introduction",
            "https://docs.enkryptai.com/get-started/introduction",
            "https://docs.enkryptai.com/api-reference/introduction",
            "https://docs.enkryptai.com/sdk-reference/python/introduction",
            "https://docs.enkryptai.com/resources/introduction"
        ]

    print(f"🚀 Incremental Scraper: Checking {len(target_urls)} pages...")
    scraped_data = await scrape_docs_concurrently(target_urls)

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    any_updated = False

    for page in scraped_data:
        if page["status"] != "success":
            continue
        
        url = page["url"]
        content = page["content"]
        new_hash = db.calculate_hash(content)
        old_hash = db.get_file_hash(url)

        if new_hash == old_hash:
            print(f"✅ Unchanged: {url}")
            continue
        
        print(f"🔄 Updating: {url} (Hash changed)")
        any_updated = True

        # 1. DELETE old chunks for this URL to prevent duplication
        try:
            # For Chroma and PGVector in LangChain, this is the standard filter delete
            vectorstore.delete(where={"source": url})
        except Exception as e:
            print(f"Warning: Could not delete old chunks for {url}: {e}")

        # 2. CHUNK and EMBED
        doc = Document(page_content=content, metadata={"source": url})
        splits = text_splitter.split_documents([doc])
        vectorstore.add_documents(splits)

        # 3. UPDATE Registry
        db.update_registry(url, new_hash, len(splits))

    # Also save to combined file for legacy support/testing
    doc_path = "/root/enkrypt_docs.txt"
    try:
        with open(doc_path, "w", encoding="utf-8") as f:
            for page in scraped_data:
                if page["status"] == "success":
                    f.write(f"\n\n### SOURCE: {page['url']} ###\n\n")
                    f.write(page["content"])
    except:
        pass

    print("✅ Scraper cycle complete.")
    return any_updated
