# Stage 5 Latency Report

## Measured Runs

Environment: `OPENROUTER_MODEL=openai/gpt-oss-120b:free`, measured after adding the new API key.
Question: `If a company breaks a contract and avoids taxes, what are the legal and regulatory consequences?`

| Run | Mode | Latency | Answer chars | Note |
|---|---:|---:|---:|---|
| Baseline | Full Stage 5, runtime `OPENROUTER_MAX_TOKENS=512`, `A2A_TIMEOUT_SECONDS=600` | 427.49s | full answer printed by `test_client.py` | Successful response with the new API key. The run was slow because the specialist agents generated long outputs before final synthesis. |
| Optimized | `LATENCY_OPTIMIZED=1`, runtime `OPENROUTER_MAX_TOKENS=512`, `A2A_TIMEOUT_SECONDS=600` | 386.48s | 3314 | Successful response. Law Agent used keyword routing and skipped the final synthesis LLM call. |

Observed latency reduction on this run: `427.49s - 386.48s = 41.01s`, about `9.59%` faster.

## Optimization Proposal

The baseline Stage 5 path spends latency on multiple LLM calls: Customer Agent routing, Law Agent legal analysis, Law Agent routing, Tax Agent, Compliance Agent, and final Law Agent synthesis. Tax and Compliance already run in parallel, so the remaining easy wins are reducing avoidable sequential LLM calls.

Applied optimization:

1. Replace the Law Agent routing LLM call with deterministic keyword routing when `LATENCY_OPTIMIZED=1`.
2. Skip the final Law Agent synthesis LLM call in demo mode and directly join the Law, Tax, and Compliance sections.
3. Keep the distributed A2A architecture unchanged: Registry, Customer Agent, Law Agent, Tax Agent, and Compliance Agent still communicate over HTTP/A2A.

Recommended production follow-ups:

- Cache discovered agent cards and registry lookups per process.
- Reuse HTTP clients for repeated A2A calls.
- Use a faster model for routing/summarization while keeping a stronger model for specialist legal analysis.
- Add streaming responses so the UI shows partial output before the full chain completes.
- Tune `OPENROUTER_MAX_TOKENS` based on answer length requirements.

## Commands

Baseline:

```bash
OPENROUTER_MAX_TOKENS=512 A2A_TIMEOUT_SECONDS=600 ./start_all.sh
A2A_TIMEOUT_SECONDS=600 uv run python test_client.py
```

Optimized:

```bash
LATENCY_OPTIMIZED=1 OPENROUTER_MAX_TOKENS=512 A2A_TIMEOUT_SECONDS=600 ./start_all.sh
LATENCY_OPTIMIZED=1 OPENROUTER_MAX_TOKENS=512 A2A_TIMEOUT_SECONDS=600 uv run python benchmark_latency.py --runs 1 --label optimized_new_key
```
