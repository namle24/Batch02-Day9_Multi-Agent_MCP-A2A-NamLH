"""
Task 3 — Convert toàn bộ file trong data/landing/ thành Markdown.

Sử dụng MarkItDown của Microsoft:
    https://github.com/microsoft/markitdown

Cài đặt:
    pip install markitdown

Hướng dẫn:
    1. Scan toàn bộ file trong data/landing/ (PDF, DOCX, JSON)
    2. Convert sang Markdown
    3. Lưu vào data/standardized/ giữ nguyên cấu trúc thư mục
"""

import json
import re
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree

try:
    from markitdown import MarkItDown
except Exception:  # pragma: no cover - optional dependency in offline tests
    MarkItDown = None

LANDING_DIR = Path(__file__).parent.parent / "data" / "landing"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "standardized"


def convert_legal_docs():
    """Convert PDF/DOCX files trong data/landing/legal/ sang markdown."""
    legal_dir = LANDING_DIR / "legal"
    output_dir = OUTPUT_DIR / "legal"
    output_dir.mkdir(parents=True, exist_ok=True)

    md = MarkItDown() if MarkItDown else None

    for filepath in sorted(legal_dir.iterdir()):
        if filepath.suffix.lower() in (".pdf", ".docx", ".doc"):
            print(f"Converting: {filepath.name}")
            output_path = output_dir / f"{filepath.stem}.md"
            body = _convert_file_to_text(filepath, md)
            title = _legal_title(filepath)
            text = _legal_header(title, filepath.name) + _clean_text(body)
            output_path.write_text(text, encoding="utf-8")
            print(f"  ✓ Saved: {output_path}")


def convert_news_articles():
    """Convert JSON crawled articles trong data/landing/news/ sang markdown."""
    news_dir = LANDING_DIR / "news"
    output_dir = OUTPUT_DIR / "news"
    output_dir.mkdir(parents=True, exist_ok=True)

    for filepath in sorted(news_dir.iterdir()):
        if filepath.suffix.lower() == ".json":
            print(f"Converting: {filepath.name}")
            data = json.loads(filepath.read_text(encoding="utf-8"))
            output_path = output_dir / f"{filepath.stem}.md"
            title = data.get("title") or "Unknown article"
            url = data.get("url") or data.get("source_url") or "N/A"
            crawled = data.get("date_crawled", "N/A")
            header = f"# {title}\n\n"
            header += f"**Article URL:** {url}\n"
            header += f"**Crawled:** {crawled}\n\n---\n\n"
            body = data.get("content_markdown", data.get("content", ""))
            content = header + _clean_text(_strip_duplicate_title(body, title))
            output_path.write_text(content, encoding="utf-8")
            print(f"  ✓ Saved: {output_path}")



def _legal_title(filepath: Path) -> str:
    titles = {
        "73luat": "Luật Phòng, chống ma túy 2021",
        "105.signed_02": "Nghị định 105/2021/NĐ-CP",
        "28-cp.signed": "Nghị định 28/CP",
        "135-vbhn-vpqh": "Văn bản hợp nhất 135/VBHN-VPQH",
    }
    return titles.get(filepath.stem, filepath.stem)


def _legal_header(title: str, filename: str) -> str:
    return f"# {title}\n\n**Document type:** legal\n**Source PDF:** {filename}\n\n---\n\n"


def _clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def _strip_duplicate_title(text: str, title: str) -> str:
    stripped = text.strip()
    if stripped.lower().startswith(f"# {title}".lower()):
        return stripped.split("\n", 1)[1].strip() if "\n" in stripped else ""
    return stripped

def _convert_file_to_text(filepath: Path, md) -> str:
    if md is not None:
        try:
            result = md.convert(str(filepath))
            if getattr(result, "text_content", ""):
                return result.text_content
        except Exception:
            pass

    if filepath.suffix.lower() == ".docx":
        return _docx_to_text(filepath)

    if filepath.suffix.lower() == ".pdf":
        return _pdf_to_text(filepath)

    raw = filepath.read_bytes()
    return raw.decode("utf-8", errors="ignore")


def _pdf_to_text(filepath: Path) -> str:
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(filepath), "-"],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.stdout.strip():
            return result.stdout
    except Exception:
        pass

    raw = filepath.read_bytes()
    decoded = raw.decode("utf-8", errors="ignore")
    if decoded.startswith("%PDF"):
        return "[Không trích xuất được nội dung PDF. Cài markitdown/pypdf hoặc dùng OCR nếu PDF là bản scan.]"
    return decoded


def _docx_to_text(filepath: Path) -> str:
    with zipfile.ZipFile(filepath) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for paragraph in root.findall(".//w:p", ns):
        texts = [node.text or "" for node in paragraph.findall(".//w:t", ns)]
        line = "".join(texts).strip()
        if line:
            paragraphs.append(line)
    text = "\n\n".join(paragraphs)
    return re.sub(r"\n{3,}", "\n\n", text)


def convert_all():
    """Convert toàn bộ files."""
    print("=" * 50)
    print("Task 3: Convert to Markdown (MarkItDown)")
    print("=" * 50)

    print("\n--- Legal Documents ---")
    convert_legal_docs()

    print("\n--- News Articles ---")
    convert_news_articles()

    print("\n✓ Done! Output tại:", OUTPUT_DIR)


if __name__ == "__main__":
    convert_all()
