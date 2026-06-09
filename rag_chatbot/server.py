from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


PROJECT_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = Path(__file__).resolve().parent / "static"
PERF_DIR = PROJECT_DIR / "data" / "performance"
PERF_LOG = PERF_DIR / "chat_metrics.jsonl"

DEFAULT_MODEL_OPTIONS = [
    "anthropic/claude-sonnet-4-5",
    "openai/gpt-4o-mini",
    "google/gemini-2.5-flash",
    "anthropic/claude-3.5-haiku",
    "meta-llama/llama-3.1-8b-instruct",
]

DEFAULT_DAY08_DIR = PROJECT_DIR / "day08_rag_pipeline"
DAY08_DIR = Path(os.getenv("DAY08_RAG_DIR", str(DEFAULT_DAY08_DIR))).expanduser().resolve()

if str(DAY08_DIR) not in sys.path:
    sys.path.insert(0, str(DAY08_DIR))

load_dotenv(PROJECT_DIR / ".env")

try:
    from src.task10_generation import _offline_answer, format_context, reorder_for_llm
    from src.task9_retrieval_pipeline import retrieve
except Exception as exc:  # pragma: no cover
    retrieve = None
    reorder_for_llm = None
    format_context = None
    _offline_answer = None
    DAY08_IMPORT_ERROR = exc
else:
    DAY08_IMPORT_ERROR = None


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=8)
    use_rag: bool = True
    model: str | None = Field(default=None, max_length=160)


class Source(BaseModel):
    title: str
    path: str
    source_type: str
    chunk_index: str
    score: float
    retrieval: str
    preview: str
    url: str = ""
    source_pdf: str = ""


class Performance(BaseModel):
    retrieval_ms: float
    generation_ms: float
    total_ms: float
    source_count: int
    cached_retrieval: bool
    mode: str
    model: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
    performance: Performance


class PerfSummary(BaseModel):
    count: int
    avg_total_ms: float
    avg_retrieval_ms: float
    avg_generation_ms: float
    p95_total_ms: float
    fastest_ms: float
    slowest_ms: float



def _normalize_model_id(model: str) -> str:
    fixes = {
        "google/gemini-2.5-flash-review": "google/gemini-2.5-flash",
        "google/gemini-2.5-flash-preview": "google/gemini-2.5-flash",
        "google/gemini-2.0-flash-001": "google/gemini-2.0-flash-001",
    }
    return fixes.get(model.strip(), model.strip())


def _model_options() -> list[str]:
    configured = os.getenv("OPENROUTER_MODEL_OPTIONS", "")
    models = [_normalize_model_id(item) for item in configured.split(",") if item.strip()]
    default_model = _normalize_model_id(os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL_OPTIONS[0]))
    models = [default_model, *models, *DEFAULT_MODEL_OPTIONS]
    deduped: list[str] = []
    for model in models:
        if model and model not in deduped:
            deduped.append(model)
    return deduped


def _selected_model(model: str | None) -> str:
    model = _normalize_model_id(model or "")
    return model or _normalize_model_id(os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL_OPTIONS[0]))


def _get_chat_llm(model: str) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        openai_api_key=os.getenv("OPENROUTER_API_KEY"),
        openai_api_base="https://openrouter.ai/api/v1",
        max_tokens=int(os.getenv("OPENROUTER_MAX_TOKENS", "1024")),
        temperature=float(os.getenv("OPENROUTER_TEMPERATURE", "0.2")),
    )

def _require_day08() -> None:
    if DAY08_IMPORT_ERROR is not None:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Cannot import Day08 RAG pipeline from {DAY08_DIR}. "
                f"Set DAY08_RAG_DIR in .env. Error: {DAY08_IMPORT_ERROR}"
            ),
        )


@lru_cache(maxsize=128)
def _retrieve_cached(query: str, top_k: int) -> tuple[dict[str, Any], ...]:
    _require_day08()
    assert retrieve is not None
    return tuple(retrieve(query, top_k=top_k))


def _history_context(history: list[ChatMessage], limit: int = 6) -> str:
    recent = history[-limit:]
    if not recent:
        return "No previous conversation."
    lines = []
    for item in recent:
        speaker = "User" if item.role == "user" else "Assistant"
        lines.append(f"{speaker}: {item.content[:800]}")
    return "\n".join(lines)


def _query_for_retrieval(message: str, history: list[ChatMessage]) -> str:
    previous_user = [item.content for item in history if item.role == "user"][-2:]
    if not previous_user:
        return message
    return " | ".join([*previous_user, message])


def _source_view(chunk: dict[str, Any]) -> Source:
    metadata = chunk.get("metadata", {})
    content = chunk.get("content", "").replace("\n", " ").strip()
    return Source(
        title=str(metadata.get("title") or metadata.get("source", "Unknown source")),
        path=str(metadata.get("path", "")),
        source_type=str(metadata.get("type", "unknown")),
        chunk_index=str(metadata.get("chunk_index", "n/a")),
        score=float(chunk.get("score", 0.0)),
        retrieval=str(chunk.get("source", "hybrid")),
        preview=content[:700],
        url=str(metadata.get("url", "")),
        source_pdf=str(metadata.get("source_pdf", "")),
    )


def _system_prompt() -> str:
    return """Bạn là Legal RAG Chatbot cho lab Day09.

Mục tiêu:
- Trò chuyện tự nhiên như chatbot bình thường, không chỉ trả về đoạn retrieve.
- Khi câu hỏi liên quan pháp luật ma túy/chất cấm/tin tức trong corpus, hãy dùng context Day08.
- Trả lời bằng tiếng Việt, rõ ý, có cấu trúc ngắn gọn.
- Với câu hỏi về bài báo/tin tức: nêu kết luận ngắn gọn và cite bằng link bài báo nếu context có Article URL.
- Với câu hỏi về luật: nêu rõ thuộc văn bản luật/nghị định nào, điều/khoản nào nếu context có.
- Không bịa điều luật hoặc link. Nếu context không đủ, nói rõ phần nào không xác minh được từ dữ liệu hiện có.
- Nếu người dùng chào hỏi hoặc hỏi follow-up chung, hãy trả lời tự nhiên và vẫn tận dụng lịch sử hội thoại.
"""


def _build_user_prompt(message: str, history: list[ChatMessage], chunks: list[dict[str, Any]]) -> str:
    ordered = reorder_for_llm(chunks) if reorder_for_llm else chunks
    context = format_context(ordered) if format_context else ""
    return f"""Conversation history:
{_history_context(history)}

Retrieved context:
{context if context else "No retrieved context."}

User message:
{message}

Answer conversationally. For news context, cite Article URL. For legal context, cite legal document name and article/clause when available."""


def _generate_answer(message: str, history: list[ChatMessage], chunks: list[dict[str, Any]], model: str) -> tuple[str, str]:
    if not os.getenv("OPENROUTER_API_KEY"):
        if _offline_answer and chunks:
            return _offline_answer(message, chunks), "offline"
        return "Chưa có OPENROUTER_API_KEY. Tôi có thể chạy retrieval, nhưng chưa thể sinh câu trả lời bằng LLM.", "offline"

    llm = _get_chat_llm(model)
    try:
        result = llm.invoke(
            [
                SystemMessage(content=_system_prompt()),
                HumanMessage(content=_build_user_prompt(message, history, chunks)),
            ]
        )
    except Exception as exc:
        message_text = str(exc)
        if "not a valid model ID" in message_text or "BadRequestError" in message_text:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Model '{model}' is not valid on OpenRouter. "
                    "Choose another model from the dropdown or use a valid OpenRouter model id, "
                    "for example google/gemini-2.5-flash."
                ),
            ) from exc
        raise
    return str(result.content), "llm"


def _append_perf(payload: dict[str, Any]) -> None:
    PERF_DIR.mkdir(parents=True, exist_ok=True)
    with PERF_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _read_perf_rows(limit: int = 200) -> list[dict[str, Any]]:
    if not PERF_LOG.exists():
        return []
    lines = PERF_LOG.read_text(encoding="utf-8").splitlines()[-limit:]
    rows = []
    for line in lines:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _summary(rows: list[dict[str, Any]]) -> PerfSummary:
    if not rows:
        return PerfSummary(
            count=0,
            avg_total_ms=0,
            avg_retrieval_ms=0,
            avg_generation_ms=0,
            p95_total_ms=0,
            fastest_ms=0,
            slowest_ms=0,
        )
    totals = sorted(float(row.get("total_ms", 0)) for row in rows)
    retrievals = [float(row.get("retrieval_ms", 0)) for row in rows]
    generations = [float(row.get("generation_ms", 0)) for row in rows]
    p95_index = min(len(totals) - 1, int(len(totals) * 0.95))
    return PerfSummary(
        count=len(rows),
        avg_total_ms=sum(totals) / len(totals),
        avg_retrieval_ms=sum(retrievals) / len(retrievals),
        avg_generation_ms=sum(generations) / len(generations),
        p95_total_ms=totals[p95_index],
        fastest_ms=totals[0],
        slowest_ms=totals[-1],
    )


app = FastAPI(title="Day09 Legal RAG Chatbot", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": DAY08_IMPORT_ERROR is None,
        "day08_dir": str(DAY08_DIR),
        "has_openrouter_key": bool(os.getenv("OPENROUTER_API_KEY")),
        "model": os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL_OPTIONS[0]),
        "model_options": _model_options(),
    }


@app.get("/api/models")
def models() -> dict[str, Any]:
    return {
        "default": os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL_OPTIONS[0]),
        "models": _model_options(),
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    started = time.perf_counter()
    retrieval_ms = 0.0
    chunks: list[dict[str, Any]] = []
    cached = False

    if request.use_rag:
        query = _query_for_retrieval(request.message, request.history)
        before_cache = _retrieve_cached.cache_info()
        t0 = time.perf_counter()
        chunks = [dict(item) for item in _retrieve_cached(query, request.top_k)]
        retrieval_ms = (time.perf_counter() - t0) * 1000
        after_cache = _retrieve_cached.cache_info()
        cached = after_cache.hits > before_cache.hits

    selected_model = _selected_model(request.model)

    t1 = time.perf_counter()
    answer, mode = _generate_answer(request.message, request.history, chunks, selected_model)
    generation_ms = (time.perf_counter() - t1) * 1000
    total_ms = (time.perf_counter() - started) * 1000

    perf = Performance(
        retrieval_ms=round(retrieval_ms, 2),
        generation_ms=round(generation_ms, 2),
        total_ms=round(total_ms, 2),
        source_count=len(chunks),
        cached_retrieval=cached,
        mode=mode,
        model=selected_model,
    )
    sources = [_source_view(chunk) for chunk in chunks]

    _append_perf(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "message_chars": len(request.message),
            "top_k": request.top_k,
            **perf.model_dump(),
        }
    )

    return ChatResponse(answer=answer, sources=sources, performance=perf)


@app.get("/api/performance", response_model=PerfSummary)
def performance() -> PerfSummary:
    return _summary(_read_perf_rows())


@app.get("/api/performance/recent")
def recent_performance() -> list[dict[str, Any]]:
    return list(reversed(_read_perf_rows(limit=30)))
