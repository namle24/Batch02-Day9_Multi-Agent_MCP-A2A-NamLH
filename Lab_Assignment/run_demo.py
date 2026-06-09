from __future__ import annotations

import argparse
from dataclasses import asdict

from supervisor_workers import ask


DEFAULT_QUESTION = "Hành vi tàng trữ ma túy bị xử lý thế nào và có bài báo nào liên quan nghệ sĩ không?"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Day08 Supervisor-Workers assignment demo.")
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--top-k", type=int, default=4)
    args = parser.parse_args()

    response = ask(args.question, top_k=args.top_k)

    print("=" * 80)
    print("SUPERVISOR - WORKERS DAY08 ASSIGNMENT")
    print("=" * 80)
    print(f"Question: {args.question}")
    print(f"Route: {', '.join(response.route)}")
    print(f"Latency: {response.latency_ms:.2f} ms")
    print(f"Mode: {response.mode} | Model: {response.model}")
    print("\nTrace:")
    for step in response.trace:
        print(f"- {step}")
    print("\nAnswer:")
    print(response.answer)
    print("\nEvidence:")
    for evidence in response.evidence:
        data = asdict(evidence)
        print(f"- [{data['worker']}] {data['title']} | {data['url'] or data['source_pdf'] or data['path']}")


if __name__ == "__main__":
    main()

