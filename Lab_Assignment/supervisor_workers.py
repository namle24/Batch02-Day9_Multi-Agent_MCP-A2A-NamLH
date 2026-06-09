"""Supervisor - Workers chatbot built on top of the Day08 corpus.

The goal of this assignment module is intentionally practical:
- keep the Day08 legal/news data surface;
- route every question through a Supervisor;
- delegate evidence gathering to 2-3 specialised Workers;
- return a normal chatbot answer, not just raw retrieval chunks;
- expose trace and latency so the interaction can be demonstrated.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI


PROJECT_DIR = Path(__file__).resolve().parents[1]
DAY08_DIR = Path(os.getenv("DAY08_RAG_DIR", PROJECT_DIR / "day08_rag_pipeline")).resolve()
STANDARDIZED_DIR = DAY08_DIR / "data" / "standardized"
PERF_DIR = Path(__file__).resolve().parent / "performance"
PERF_LOG = PERF_DIR / "supervisor_metrics.jsonl"

TOKEN_RE = re.compile(r"[\wÀ-ỹ]+", re.UNICODE)


@dataclass
class Evidence:
    worker: str
    title: str
    source_type: str
    path: str
    score: float
    preview: str
    url: str = ""
    source_pdf: str = ""


@dataclass
class WorkerResult:
    worker: str
    latency_ms: float
    evidence: list[Evidence] = field(default_factory=list)
    note: str = ""


@dataclass
class SupervisorResponse:
    answer: str
    route: list[str]
    trace: list[str]
    evidence: list[Evidence]
    latency_ms: float
    worker_latencies_ms: dict[str, float]
    mode: str
    model: str


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def extract_metadata(content: str, path: Path, source_type: str) -> dict[str, str]:
    metadata: dict[str, str] = {
        "title": path.stem,
        "path": str(path.relative_to(STANDARDIZED_DIR)),
        "type": source_type,
    }
    title_match = re.search(r"^#\s+(.+)$", content, flags=re.M)
    if title_match:
        metadata["title"] = title_match.group(1).strip()
    patterns = {
        "url": r"^\*\*(?:Article URL|Source):\*\*\s*(.+)$",
        "source_pdf": r"^\*\*Source PDF:\*\*\s*(.+)$",
        "document_type": r"^\*\*Document type:\*\*\s*(.+)$",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, content, flags=re.M)
        if match:
            metadata[key] = match.group(1).strip()
    return metadata


def load_documents() -> list[dict]:
    documents: list[dict] = []
    if not STANDARDIZED_DIR.exists():
        return documents
    for md_path in sorted(STANDARDIZED_DIR.rglob("*.md")):
        if md_path.name.startswith("."):
            continue
        content = md_path.read_text(encoding="utf-8").strip()
        if not content:
            continue
        relative = md_path.relative_to(STANDARDIZED_DIR)
        source_type = relative.parts[0] if len(relative.parts) > 1 else "unknown"
        documents.append(
            {
                "content": content,
                "metadata": extract_metadata(content, md_path, source_type),
                "tokens": tokenize(content),
            }
        )
    return documents


def score_document(query_tokens: list[str], doc_tokens: list[str]) -> float:
    if not query_tokens or not doc_tokens:
        return 0.0
    query_counts = Counter(query_tokens)
    doc_counts = Counter(doc_tokens)
    overlap = sum(min(query_counts[t], doc_counts[t]) for t in query_counts)
    coverage = overlap / max(1, len(set(query_tokens)))
    density = overlap / math.sqrt(max(1, len(doc_tokens)))
    return coverage + density


def trim_preview(text: str, max_chars: int = 720) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


class BaseWorker:
    name = "base"
    source_type = "unknown"

    def __init__(self, documents: list[dict]) -> None:
        self.documents = [doc for doc in documents if doc["metadata"].get("type") == self.source_type]

    def run(self, question: str, top_k: int = 4) -> WorkerResult:
        started = time.perf_counter()
        query_tokens = tokenize(question)
        ranked: list[tuple[float, dict]] = []
        for doc in self.documents:
            score = score_document(query_tokens, doc["tokens"])
            if score > 0:
                ranked.append((score, doc))
        ranked.sort(key=lambda item: item[0], reverse=True)
        evidence = [
            Evidence(
                worker=self.name,
                title=doc["metadata"].get("title", doc["metadata"].get("path", "unknown")),
                source_type=doc["metadata"].get("type", self.source_type),
                path=doc["metadata"].get("path", ""),
                score=round(score, 4),
                preview=trim_preview(doc["content"]),
                url=doc["metadata"].get("url", ""),
                source_pdf=doc["metadata"].get("source_pdf", ""),
            )
            for score, doc in ranked[:top_k]
        ]
        latency_ms = (time.perf_counter() - started) * 1000
        return WorkerResult(worker=self.name, latency_ms=latency_ms, evidence=evidence)


class LegalWorker(BaseWorker):
    name = "legal_worker"
    source_type = "legal"


class NewsWorker(BaseWorker):
    name = "news_worker"
    source_type = "news"


class ConversationWorker:
    name = "conversation_worker"

    def run(self, question: str, top_k: int = 4) -> WorkerResult:
        started = time.perf_counter()
        note = (
            "Câu hỏi có thể cần trả lời hội thoại tự nhiên. Worker này giữ vai trò "
            "bổ sung intent, không lấy evidence từ corpus."
        )
        return WorkerResult(worker=self.name, latency_ms=(time.perf_counter() - started) * 1000, note=note)


class Supervisor:
    """Route questions to workers and synthesize final chatbot answers."""

    def __init__(self) -> None:
        load_dotenv(PROJECT_DIR / ".env")
        self.documents = load_documents()
        self.legal_worker = LegalWorker(self.documents)
        self.news_worker = NewsWorker(self.documents)
        self.conversation_worker = ConversationWorker()
        self.model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")

    def route(self, question: str) -> list[str]:
        q = question.lower()
        legal_keywords = ["luật", "điều", "khoản", "nghị định", "hình sự", "xử phạt", "ma túy", "ma tuý"]
        news_keywords = ["bài báo", "tin", "nghệ sĩ", "ca sĩ", "showbiz", "link", "nguồn", "vụ"]
        routes: list[str] = []
        if any(keyword in q for keyword in legal_keywords):
            routes.append("legal_worker")
        if any(keyword in q for keyword in news_keywords):
            routes.append("news_worker")
        if not routes or any(keyword in q for keyword in ["chào", "hello", "giải thích", "tóm tắt"]):
            routes.append("conversation_worker")
        return routes

    def ask(self, question: str, top_k: int = 4) -> SupervisorResponse:
        started = time.perf_counter()
        route = self.route(question)
        trace = [f"Supervisor nhận câu hỏi: {question}", f"Supervisor route -> {', '.join(route)}"]
        results: list[WorkerResult] = []

        for worker_name in route:
            worker = getattr(self, worker_name)
            result = worker.run(question, top_k=top_k)
            results.append(result)
            trace.append(
                f"{worker_name} hoàn tất trong {result.latency_ms:.1f} ms, "
                f"evidence={len(result.evidence)}"
            )

        evidence = dedupe_evidence(item for result in results for item in result.evidence)
        answer, mode = self._synthesize(question, route, evidence, trace)
        latency_ms = (time.perf_counter() - started) * 1000
        response = SupervisorResponse(
            answer=answer,
            route=route,
            trace=trace,
            evidence=evidence,
            latency_ms=latency_ms,
            worker_latencies_ms={result.worker: round(result.latency_ms, 2) for result in results},
            mode=mode,
            model=self.model,
        )
        self._append_perf(response)
        return response

    def _synthesize(self, question: str, route: list[str], evidence: list[Evidence], trace: list[str]) -> tuple[str, str]:
        context = format_evidence(evidence)
        if not os.getenv("OPENROUTER_API_KEY"):
            return offline_answer(question, route, evidence), "offline"

        llm = ChatOpenAI(
            model=self.model,
            openai_api_key=os.getenv("OPENROUTER_API_KEY"),
            openai_api_base="https://openrouter.ai/api/v1",
            max_tokens=int(os.getenv("OPENROUTER_MAX_TOKENS", "700")),
            temperature=float(os.getenv("OPENROUTER_TEMPERATURE", "0.2")),
        )
        messages = [
            SystemMessage(
                content=(
                    "Bạn là Supervisor của hệ chatbot pháp lý Day08 cải tiến. "
                    "Trả lời tự nhiên bằng tiếng Việt. Nếu dùng văn bản luật, nêu rõ văn bản/điều khoản khi context có. "
                    "Nếu dùng bài báo, ưu tiên nêu link bài báo nếu context có URL. Không bịa nguồn."
                )
            ),
            HumanMessage(
                content=(
                    f"Câu hỏi: {question}\n\n"
                    f"Workers đã gọi: {', '.join(route)}\n\n"
                    f"Evidence:\n{context if context else 'Không có evidence phù hợp.'}\n\n"
                    "Hãy trả lời ngắn gọn, có bullet nếu cần."
                )
            ),
        ]
        try:
            result = llm.invoke(messages)
        except Exception as exc:
            trace.append(f"LLM lỗi, fallback offline: {exc}")
            return offline_answer(question, route, evidence), "offline_fallback"
        return str(result.content), "llm"

    def _append_perf(self, response: SupervisorResponse) -> None:
        PERF_DIR.mkdir(parents=True, exist_ok=True)
        row = {
            **asdict(response),
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "evidence": [asdict(item) for item in response.evidence],
        }
        with PERF_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def dedupe_evidence(items: Iterable[Evidence]) -> list[Evidence]:
    seen: set[tuple[str, str]] = set()
    output: list[Evidence] = []
    for item in sorted(items, key=lambda e: e.score, reverse=True):
        key = (item.path, item.worker)
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output[:8]


def format_evidence(evidence: list[Evidence]) -> str:
    lines = []
    for index, item in enumerate(evidence, 1):
        source = item.url or item.source_pdf or item.path
        lines.append(
            f"[{index}] worker={item.worker}; title={item.title}; type={item.source_type}; "
            f"score={item.score}; source={source}\n{item.preview}"
        )
    return "\n\n".join(lines)


def offline_answer(question: str, route: list[str], evidence: list[Evidence]) -> str:
    if not evidence:
        return (
            "Supervisor đã xử lý câu hỏi theo hướng hội thoại, nhưng chưa tìm thấy evidence phù hợp "
            "trong corpus Day08. Bạn có thể hỏi cụ thể hơn về luật ma túy, nghị định hoặc bài báo."
        )
    lines = [
        "Supervisor đã tổng hợp từ các worker sau: " + ", ".join(route) + ".",
        "",
        "Các nguồn/evidence nổi bật:",
    ]
    for item in evidence[:4]:
        source = item.url or item.source_pdf or item.path
        lines.append(f"- {item.title} ({item.source_type}, score={item.score}): {source}")
    lines.extend(
        [
            "",
            "Kết luận ngắn: câu hỏi cần đối chiếu cả nhóm nguồn pháp luật và/hoặc bài báo. "
            "Khi trả lời chính thức bằng LLM, hệ thống sẽ nêu rõ văn bản luật hoặc link bài báo nếu context có.",
        ]
    )
    return "\n".join(lines)


def ask(question: str, top_k: int = 4) -> SupervisorResponse:
    return Supervisor().ask(question, top_k=top_k)

