"""Benchmark Stage 5 end-to-end latency via the Customer Agent.

Run after ./start_all.sh is already running.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
from a2a.client import A2AClient
from a2a.types import AgentCard, Message, MessageSendParams, Part, Role, SendMessageRequest, TextPart
from dotenv import load_dotenv

load_dotenv()

CUSTOMER_AGENT_URL = os.getenv("CUSTOMER_AGENT_URL", "http://localhost:10100")
A2A_TIMEOUT_SECONDS = float(os.getenv("A2A_TIMEOUT_SECONDS", "600"))
DEFAULT_QUESTION = (
    "If a company breaks a contract and avoids taxes, "
    "what are the legal and regulatory consequences?"
)
RESULTS_PATH = Path("data/performance/stage5_latency.jsonl")


def extract_text(response: object) -> str:
    text = ""
    root = getattr(response, "root", response)
    result = getattr(root, "result", None)
    if result is None:
        return text
    artifacts = getattr(result, "artifacts", None)
    if artifacts:
        for artifact in artifacts:
            for part in getattr(artifact, "parts", []) or []:
                inner = getattr(part, "root", part)
                text += getattr(inner, "text", "") or ""
    if not text:
        for part in getattr(result, "parts", []) or []:
            inner = getattr(part, "root", part)
            text += getattr(inner, "text", "") or ""
    return text


async def send_once(question: str) -> tuple[float, int]:
    async with httpx.AsyncClient(timeout=A2A_TIMEOUT_SECONDS) as http_client:
        card_resp = await http_client.get(f"{CUSTOMER_AGENT_URL}/.well-known/agent.json")
        card_resp.raise_for_status()
        agent_card = AgentCard.model_validate(card_resp.json())
        client = A2AClient(httpx_client=http_client, agent_card=agent_card)
        message = Message(
            role=Role.user,
            parts=[Part(root=TextPart(text=question))],
            message_id=str(uuid4()),
        )
        request = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(message=message),
        )
        started = time.perf_counter()
        response = await client.send_message(request)
        elapsed = time.perf_counter() - started
        return elapsed, len(extract_text(response))


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--label", default=os.getenv("LATENCY_LABEL", "baseline"))
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    args = parser.parse_args()

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    latencies = []
    for index in range(1, args.runs + 1):
        elapsed, chars = await send_once(args.question)
        latencies.append(elapsed)
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "label": args.label,
            "run": index,
            "latency_seconds": round(elapsed, 3),
            "answer_chars": chars,
            "optimized": os.getenv("LATENCY_OPTIMIZED", "0"),
            "model": os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4-5"),
        }
        with RESULTS_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"run={index} label={args.label} latency={elapsed:.2f}s answer_chars={chars}")

    avg = sum(latencies) / len(latencies)
    print(f"AVERAGE_LATENCY_SECONDS={avg:.2f}")
    print(f"RESULTS_FILE={RESULTS_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
