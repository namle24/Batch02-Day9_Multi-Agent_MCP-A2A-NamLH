"""
Task 6 — Lexical Search Module (BM25).

Mặc định sử dụng BM25. Nếu dùng phương pháp khác (TF-IDF, Elasticsearch,
Weaviate BM25 built-in), hãy giải thích cơ chế trong buổi demo → +5 bonus.

Cài đặt:
    pip install rank-bm25

BM25 hoạt động thế nào:
    - Term Frequency (TF): từ xuất hiện nhiều trong document → điểm cao
    - Inverse Document Frequency (IDF): từ hiếm → quan trọng hơn
    - Document length normalization: document dài không bị ưu tiên quá mức
    - Formula: score(q,d) = Σ IDF(qi) * (tf(qi,d) * (k1+1)) / (tf(qi,d) + k1*(1-b+b*|d|/avgdl))
    - k1=1.5 (term saturation), b=0.75 (length normalization)
"""

import math
from collections import Counter
from functools import lru_cache

from .local_retrieval import corpus_idf, cosine_from_counters, get_chunks, tokenize

CORPUS: list[dict] = []  # Lazy-loaded list of {'content': str, 'metadata': dict}


def _get_corpus() -> list[dict]:
    global CORPUS
    if not CORPUS:
        CORPUS = list(get_chunks())
    return CORPUS


def build_bm25_index(corpus: list[dict]):
    """
    Xây dựng BM25 index từ corpus.

    Args:
        corpus: List of {'content': str, 'metadata': dict}
    """
    tokenized = [tokenize(doc["content"]) for doc in corpus]
    doc_freq: Counter = Counter()
    for tokens in tokenized:
        doc_freq.update(set(tokens))
    avgdl = sum(len(tokens) for tokens in tokenized) / max(1, len(tokenized))
    return {
        "tokenized": tokenized,
        "doc_freq": doc_freq,
        "avgdl": avgdl,
        "n_docs": len(tokenized),
    }


@lru_cache(maxsize=1)
def _cached_bm25_index():
    return build_bm25_index(tuple(_get_corpus()))


@lru_cache(maxsize=1)
def _cached_tfidf_index():
    corpus = tuple(_get_corpus())
    tokenized_docs = tuple(tuple(tokenize(doc["content"])) for doc in corpus)
    idf = corpus_idf([list(tokens) for tokens in tokenized_docs])
    return corpus, tokenized_docs, idf


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    """
    Tìm kiếm từ khóa sử dụng BM25.

    Args:
        query: Câu truy vấn
        top_k: Số lượng kết quả tối đa

    Returns:
        List of {
            'content': str,
            'score': float,      # BM25 score
            'metadata': dict
        }
        Sorted by score descending.
    """
    corpus = _get_corpus()
    if not corpus or top_k <= 0:
        return []

    index = _cached_bm25_index()
    query_tokens = tokenize(query)
    k1 = 1.5
    b = 0.75
    scores: list[float] = []

    for tokens in index["tokenized"]:
        tf = Counter(tokens)
        doc_len = len(tokens)
        score = 0.0
        for term in query_tokens:
            if term not in tf:
                continue
            df = index["doc_freq"].get(term, 0)
            idf = math.log((index["n_docs"] - df + 0.5) / (df + 0.5) + 1)
            denom = tf[term] + k1 * (1 - b + b * doc_len / max(index["avgdl"], 1))
            score += idf * (tf[term] * (k1 + 1)) / denom
        scores.append(score)

    ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)
    results = []
    for idx, score in ranked[:top_k]:
        if score <= 0:
            continue
        results.append({
            "content": corpus[idx]["content"],
            "score": float(score),
            "metadata": dict(corpus[idx].get("metadata", {})),
        })
    return results


def tfidf_lexical_search(query: str, top_k: int = 10) -> list[dict]:
    """
    Bonus lexical alternative: TF-IDF cosine search.

    TF-IDF weights frequent query/document terms by inverse document frequency,
    then ranks chunks by cosine similarity. Unlike BM25, this implementation
    does not use term saturation or document-length normalization parameters.
    """
    corpus, tokenized_docs, idf = _cached_tfidf_index()
    if not corpus or top_k <= 0:
        return []

    query_vector = Counter(tokenize(query))

    results = []
    for doc, tokens in zip(corpus, tokenized_docs):
        score = cosine_from_counters(query_vector, Counter(tokens), idf)
        if score <= 0:
            continue
        results.append({
            "content": doc["content"],
            "score": float(score),
            "metadata": dict(doc.get("metadata", {})),
            "source": "tfidf",
        })

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]


if __name__ == "__main__":
    # Test
    results = lexical_search("Điều 248 tàng trữ trái phép chất ma tuý", top_k=5)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")
