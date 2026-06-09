"""
Task 2 — Crawl bài báo về nghệ sĩ liên quan tới ma tuý.

Hướng dẫn:
    1. Crawl tối thiểu 5 bài báo từ các trang tin tức Việt Nam.
    2. Sử dụng Crawl4AI hoặc thư viện crawling tương tự.
    3. Lưu output vào data/landing/news/
    4. Mỗi bài lưu 1 file JSON với metadata (url, title, date_crawled, content).

Cài đặt:
    pip install crawl4ai
"""

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"
URLS_FILE = DATA_DIR / "article_urls.txt"


def setup_directory():
    """Tạo thư mục data/landing/news/ nếu chưa có."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


# TODO: Điền danh sách URL bài báo cần crawl
ARTICLE_URLS = [
    "https://vnexpress.net/ma-tuy-trong-loi-song-showbiz-5074606.html",
    "https://thanhnien.vn/ma-tuy-va-showbiz-su-thanh-loc-can-bat-dau-tu-nghe-si-185260513123425952.htm",
    "https://vnexpress.net/ca-si-long-nhat-son-ngoc-minh-bi-bat-vi-lien-quan-ma-tuy-5060857.html",
    "https://vnexpress.net/anh-em-ca-si-chi-dan-ru-nhieu-nguoi-choi-ma-tuy-nhu-the-nao-4929804.html",
    "https://ngoisao.vnexpress.net/nhung-nghe-si-viet-nga-ngua-vi-ma-tuy-4816068.html",
    "https://vnexpress.net/ca-si-miu-le-bi-bat-voi-cao-buoc-to-chuc-su-dung-ma-tuy-5074769.html",
]


def load_article_urls() -> list[str]:
    """Load URLs từ ARTICLE_URLS và optional data/landing/news/article_urls.txt."""
    urls = list(ARTICLE_URLS)
    if URLS_FILE.exists():
        for line in URLS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    seen = set()
    unique = []
    for url in urls:
        if url not in seen:
            unique.append(url)
            seen.add(url)
    return unique


def slugify_url(url: str) -> str:
    path = urlparse(url).path.rsplit("/", 1)[-1] or urlparse(url).netloc
    path = re.sub(r"\.(html?|shtml)$", "", path, flags=re.I)
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", path).strip("-").lower()
    return slug[:90] or "article"


async def crawl_article(url: str) -> dict:
    """
    Crawl một bài báo và trả về dict chứa metadata + content.

    Returns:
        {
            "url": str,
            "title": str,
            "date_crawled": str (ISO format),
            "content_markdown": str
        }
    """
    try:
        from crawl4ai import AsyncWebCrawler

        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url)
            return {
                "url": url,
                "title": result.metadata.get("title", "Unknown"),
                "date_crawled": datetime.now().isoformat(),
                "content_markdown": result.markdown,
            }
    except Exception:
        # Fallback nhẹ để script vẫn dùng được khi Crawl4AI/browser chưa sẵn sàng.
        import requests

        response = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        html = response.text
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
        title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else "Unknown"
        text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.I | re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return {
            "url": url,
            "title": title,
            "date_crawled": datetime.now().isoformat(),
            "content_markdown": f"# {title}\n\n{text}",
        }


async def crawl_all():
    """Crawl toàn bộ bài báo trong ARTICLE_URLS/article_urls.txt, không đè file cũ."""
    setup_directory()
    urls = load_article_urls()

    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] Crawling: {url}")
        article = await crawl_article(url)

        filename = f"article_{slugify_url(url)}.json"
        filepath = DATA_DIR / filename
        suffix = 2
        while filepath.exists():
            existing = json.loads(filepath.read_text(encoding="utf-8"))
            if existing.get("url") == url:
                break
            filepath = DATA_DIR / f"article_{slugify_url(url)}_{suffix}.json"
            suffix += 1
        filepath.write_text(json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✓ Saved: {filepath}")


if __name__ == "__main__":
    if not load_article_urls():
        print("⚠ Hãy điền ARTICLE_URLS trước khi chạy!")
        print("Gợi ý: tìm bài báo trên VnExpress, Tuổi Trẻ, Thanh Niên, ...")
    else:
        asyncio.run(crawl_all())
