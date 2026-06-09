"""
Task 4 — Chunking & Indexing vào Vector Store.

Hướng dẫn:
    1. Đọc toàn bộ markdown files từ data/standardized/
    2. Chọn 1 chunking strategy (giải thích lý do)
    3. Chọn 1 embedding model (giải thích lý do)
    4. Index vào vector store (Weaviate khuyến cáo)

Chunking options (langchain-text-splitters):
    - RecursiveCharacterTextSplitter: an toàn, phổ biến
    - MarkdownHeaderTextSplitter: tốt cho file có heading
    - SemanticChunker: dùng embedding để tách (nâng cao)

Embedding model options:
    - sentence-transformers/all-MiniLM-L6-v2 (384 dim, nhẹ)
    - BAAI/bge-m3 (1024 dim, multilingual, tốt cho tiếng Việt)
    - OpenAI text-embedding-3-small (1536 dim, API)

Vector store options:
    - Weaviate (khuyến cáo: hỗ trợ hybrid search built-in)
    - ChromaDB (đơn giản, local)
    - FAISS (chỉ dense search)

Cài đặt:
    pip install langchain-text-splitters sentence-transformers weaviate-client
"""

from pathlib import Path

from .local_retrieval import read_markdown_documents, recursive_chunk_text, save_chunks

STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"


# =============================================================================
# CONFIGURATION — Giải thích lựa chọn của bạn trong comment
# =============================================================================

# RecursiveCharacter-style splitting is robust for mixed legal/news markdown:
# it keeps short legal clauses together while still splitting long paragraphs.
CHUNK_SIZE = 500        # Small enough for precise citation snippets in tests/demo.
CHUNK_OVERLAP = 50      # Preserves clause continuity without duplicating too much.
CHUNKING_METHOD = "recursive"  # "recursive" | "markdown_header" | "semantic"

# Offline embedding for the lab runner: hashed TF-IDF vectors. In production,
# swap this for BAAI/bge-m3 (1024 dim), which is multilingual and better for VI.
EMBEDDING_MODEL = "local-hashed-tfidf"
EMBEDDING_DIM = 384

# Local JSON vector store keeps automated tests deterministic without Docker/API.
VECTOR_STORE = "local-json"  # "weaviate" | "chromadb" | "faiss" | "local-json"


# =============================================================================
# IMPLEMENTATION
# =============================================================================

def load_documents() -> list[dict]:
    """
    Đọc toàn bộ markdown files từ data/standardized/.

    Returns:
        List of {'content': str, 'metadata': {'source': str, 'type': str}}
    """
    return read_markdown_documents()


def chunk_documents(documents: list[dict]) -> list[dict]:
    """
    Chunk documents theo strategy đã chọn.

    Returns:
        List of {'content': str, 'metadata': dict} — mỗi item là 1 chunk
    """
    chunks = []
    for doc in documents:
        splits = recursive_chunk_text(doc["content"], CHUNK_SIZE, CHUNK_OVERLAP)
        for i, chunk_text in enumerate(splits):
            chunks.append({
                "content": chunk_text,
                "metadata": {**doc["metadata"], "chunk_index": i}
            })
    return chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """
    Embed toàn bộ chunks bằng model đã chọn.

    Returns:
        Mỗi chunk dict được thêm key 'embedding': list[float]
    """
    from .local_retrieval import expanded_tokens

    embedded = []
    for chunk in chunks:
        vector = [0.0] * EMBEDDING_DIM
        for token in expanded_tokens(chunk["content"]):
            vector[hash(token) % EMBEDDING_DIM] += 1.0
        norm = sum(v * v for v in vector) ** 0.5 or 1.0
        item = chunk.copy()
        item["embedding"] = [v / norm for v in vector]
        embedded.append(item)
    return embedded


def index_to_vectorstore(chunks: list[dict]):
    """
    Lưu chunks vào vector store đã chọn.
    """
    save_chunks(chunks)


def run_pipeline():
    """Chạy toàn bộ pipeline: load → chunk → embed → index."""
    print("=" * 50)
    print("Task 4: Chunking & Indexing")
    print(f"  Chunking: {CHUNKING_METHOD} (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    print(f"  Embedding: {EMBEDDING_MODEL} (dim={EMBEDDING_DIM})")
    print(f"  Vector Store: {VECTOR_STORE}")
    print("=" * 50)

    docs = load_documents()
    print(f"\n✓ Loaded {len(docs)} documents")

    chunks = chunk_documents(docs)
    print(f"✓ Created {len(chunks)} chunks")

    chunks = embed_chunks(chunks)
    print(f"✓ Embedded {len(chunks)} chunks")

    index_to_vectorstore(chunks)
    print("✓ Indexed to vector store")


if __name__ == "__main__":
    run_pipeline()
