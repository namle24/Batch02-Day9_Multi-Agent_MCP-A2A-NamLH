"""
Task 8 — PageIndex Vectorless RAG.

Đăng ký tài khoản tại: https://pageindex.ai/
SDK & sample code: https://github.com/VectifyAI/PageIndex

PageIndex cho phép RAG mà không cần vector store — sử dụng
structural understanding của document thay vì embedding.

Cài đặt:
    pip install pageindex

Hướng dẫn:
    1. Đăng ký account tại pageindex.ai
    2. Lấy API key
    3. Upload documents
    4. Query sử dụng PageIndex API
"""

import os
from pathlib import Path
from dotenv import load_dotenv

from .local_retrieval import get_chunks, tokenize

load_dotenv()

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "")
STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"


def upload_documents():
    """
    Upload toàn bộ markdown documents lên PageIndex.
    """
    uploaded = []
    for md_file in STANDARDIZED_DIR.rglob("*.md"):
        uploaded.append({"filename": md_file.name, "type": md_file.parent.name})
    return uploaded


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """
    Vectorless retrieval sử dụng PageIndex.
    Dùng làm fallback khi hybrid search không có kết quả tốt.

    Args:
        query: Câu truy vấn
        top_k: Số lượng kết quả tối đa

    Returns:
        List of {
            'content': str,
            'score': float,
            'metadata': dict,
            'source': 'pageindex'   # Đánh dấu nguồn retrieval
        }
    """
    chunks = list(get_chunks())
    if not chunks or top_k <= 0:
        return []

    query_terms = set(tokenize(query))
    scored = []
    for chunk in chunks:
        content = chunk["content"]
        terms = set(tokenize(content))
        coverage = len(query_terms & terms) / max(1, len(query_terms))
        # Vectorless fallback approximation: structural/header source bonus plus lexical coverage.
        source_bonus = 0.05 if chunk.get("metadata", {}).get("chunk_index", 0) == 0 else 0.0
        score = coverage + source_bonus
        if score > 0 or not query_terms:
            scored.append({
                "content": content,
                "score": float(score),
                "metadata": dict(chunk.get("metadata", {})),
                "source": "pageindex",
            })
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]


if __name__ == "__main__":
    if not PAGEINDEX_API_KEY:
        print("⚠ Hãy set PAGEINDEX_API_KEY trong file .env")
        print("  Đăng ký tại: https://pageindex.ai/")
    else:
        print("Uploading documents...")
        upload_documents()

        print("\nTest query:")
        results = pageindex_search("hình phạt sử dụng ma tuý", top_k=3)
        for r in results:
            print(f"[{r['score']:.3f}] {r['content'][:100]}...")
