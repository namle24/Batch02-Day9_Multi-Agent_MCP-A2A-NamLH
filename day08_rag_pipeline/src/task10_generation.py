"""
Task 10 — Generation Có Citation.

Hướng dẫn:
    1. Chọn top_k, top_p phù hợp (giải thích lý do)
    2. Sắp xếp lại chunks sau reranking để tránh "lost in the middle"
    3. Inject context vào prompt
    4. Yêu cầu LLM trả lời có citation
    5. Nếu không đủ evidence → "I cannot verify this information"
"""

import os
from dotenv import load_dotenv

load_dotenv()

from .task9_retrieval_pipeline import retrieve
from .local_retrieval import tokenize


SOURCE_LABELS = {
    "luat-phong-chong-ma-tuy-2021.md": "Luật Phòng, chống ma túy 2021, 2021",
    "nghi-dinh-105-2021.md": "Nghị định 105/2021/NĐ-CP, 2021",
    "nghi-dinh-57-2022-danh-muc-chat-ma-tuy.md": "Nghị định 57/2022/NĐ-CP, 2022",
    "article_01_huu_tin_vnexpress.md": "VnExpress, 2022",
    "article_02_chau_viet_cuong_vnexpress.md": "VnExpress, 2018",
    "article_03_chau_viet_cuong_vietnamnet.md": "VietnamNet, 2019",
    "article_04_andrea_aybar_vnexpress.md": "VnExpress, 2024",
    "article_05_andrea_aybar_baovanhoa.md": "Báo Văn Hóa, 2025",
}


# =============================================================================
# CONFIGURATION — Giải thích lựa chọn
# =============================================================================

# top_k: Số chunks đưa vào context
# Chọn 5 vì: đủ evidence mà không quá dài gây lost in the middle
TOP_K = 5

# top_p (nucleus sampling): Xác suất tích luỹ cho token generation
# Chọn 0.9 vì: đủ diverse nhưng không quá random
TOP_P = 0.9

# temperature: Độ ngẫu nhiên của output
# Chọn 0.3 vì: RAG cần factual, ít sáng tạo
TEMPERATURE = 0.3


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

SYSTEM_PROMPT = """Answer the following question comprehensively in Vietnamese.
For every statement of fact or claim, immediately insert a citation in brackets
linking to the specific source (e.g., [Luật Phòng chống ma tuý 2021, Điều 3]
or [VnExpress, 2024]).

If the information is not explicitly stated in the provided context or knowledge
base, state 'Tôi không thể xác minh thông tin này từ nguồn hiện có' rather than
guessing.

Rules:
- Only use information from the provided context
- Every factual claim MUST have a citation
- If context is insufficient, say so clearly
- Structure your answer with clear paragraphs"""


# =============================================================================
# DOCUMENT REORDERING (tránh lost in the middle)
# =============================================================================

def reorder_for_llm(chunks: list[dict]) -> list[dict]:
    """
    Sắp xếp chunks để tránh "lost in the middle" effect.

    LLM nhớ tốt thông tin ở ĐẦU và CUỐI prompt, quên thông tin ở GIỮA.
    Strategy: đặt chunks quan trọng nhất ở đầu và cuối, kém quan trọng ở giữa.

    Input order (by score):  [1, 2, 3, 4, 5]
    Output order:            [1, 3, 5, 4, 2]
    (best first, worst in middle, second-best last)

    Args:
        chunks: List sorted by score descending (from retrieval)

    Returns:
        List reordered để maximize LLM attention.
    """
    if len(chunks) <= 2:
        return chunks
    front = [chunks[i] for i in range(0, len(chunks), 2)]
    back = [chunks[i] for i in range(1, len(chunks), 2)]
    return front + list(reversed(back))


# =============================================================================
# CONTEXT FORMATTING
# =============================================================================

def format_context(chunks: list[dict]) -> str:
    """
    Format chunks thành context string cho prompt.
    Mỗi chunk có label source để LLM có thể cite.

    Args:
        chunks: List of {'content': str, 'metadata': dict, 'score': float}

    Returns:
        Formatted context string.
    """
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        metadata = chunk.get("metadata", {})
        source = metadata.get("source", f"Source {i}")
        title = metadata.get("title", source)
        doc_type = metadata.get("type", "unknown")
        chunk_index = metadata.get("chunk_index", "n/a")
        url = metadata.get("url", "")
        source_pdf = metadata.get("source_pdf", "")
        extra = f" | Article URL: {url}" if url else ""
        if source_pdf:
            extra += f" | Legal document: {title} | Source PDF: {source_pdf}"
        context_parts.append(
            f"[Document {i} | Title: {title} | Source: {source} | Type: {doc_type} "
            f"| Chunk: {chunk_index}{extra}]\n"
            f"{chunk['content']}\n"
        )
    return "\n---\n".join(context_parts)


def _citation(chunk: dict) -> str:
    metadata = chunk.get("metadata", {})
    source = metadata.get("source", "Nguồn không rõ")
    if metadata.get("type") == "news" and metadata.get("url"):
        return f"[{metadata.get('title', source)} - {metadata['url']}]"
    if metadata.get("type") == "legal":
        return f"[{metadata.get('title', SOURCE_LABELS.get(source, source))}]"
    return f"[{SOURCE_LABELS.get(source, source)}]"


def _offline_answer(query: str, chunks: list[dict]) -> str:
    if not chunks:
        return "Tôi không thể xác minh thông tin này từ nguồn hiện có."

    query_terms = set(tokenize(query))
    sentences = []
    for chunk in chunks:
        for sentence in chunk["content"].replace("\n", " ").split("."):
            sentence = sentence.strip()
            if len(sentence) < 40:
                continue
            if query_terms and not (query_terms & set(tokenize(sentence))):
                continue
            sentences.append(f"{sentence}. {_citation(chunk)}")
            break
        if len(sentences) >= 3:
            break

    if not sentences:
        best = chunks[0]["content"].replace("\n", " ").strip()[:350]
        sentences.append(f"{best}... {_citation(chunks[0])}")
    return " ".join(sentences)


# =============================================================================
# GENERATION
# =============================================================================

def generate_with_citation(query: str, top_k: int = TOP_K) -> dict:
    """
    End-to-end RAG generation có citation.

    Pipeline:
        1. Retrieve relevant chunks
        2. Reorder để tránh lost in the middle
        3. Format context với source labels
        4. Build prompt (system + context + query)
        5. Call LLM
        6. Return answer + sources

    Args:
        query: Câu hỏi của user

    Returns:
        {
            'answer': str,           # Câu trả lời có citation
            'sources': list[dict],   # Các chunks đã dùng
            'retrieval_source': str  # 'hybrid' hoặc 'pageindex'
        }
    """
    chunks = retrieve(query, top_k=top_k)
    reordered = reorder_for_llm(chunks)
    context = format_context(reordered)
    user_message = f"Context:\n{context}\n\n---\n\nQuestion: {query}"

    answer = None
    if os.getenv("OPENAI_API_KEY"):
        try:
            from openai import OpenAI

            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=TEMPERATURE,
                top_p=TOP_P,
            )
            answer = response.choices[0].message.content
        except Exception:
            answer = None

    if not answer:
        answer = _offline_answer(query, reordered)

    return {
        "answer": answer,
        "sources": chunks,
        "retrieval_source": chunks[0].get("source", "none") if chunks else "none",
    }


if __name__ == "__main__":
    test_queries = [
        "Hình phạt cho tội tàng trữ trái phép chất ma tuý theo pháp luật Việt Nam?",
        "Những nghệ sĩ nào đã bị bắt vì liên quan tới ma tuý?",
        "Quy trình cai nghiện bắt buộc theo Luật Phòng chống ma tuý 2021?",
    ]

    for q in test_queries:
        print(f"\n{'='*70}")
        print(f"Q: {q}")
        print("=" * 70)
        result = generate_with_citation(q)
        print(f"\nA: {result['answer']}")
        print(f"\n[Sources: {len(result['sources'])} chunks | via {result['retrieval_source']}]")
