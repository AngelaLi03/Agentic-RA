# Agentic-RA — Production-Grade Agentic Research Assistant

This file primes Claude Code with project context. Read it before suggesting changes.

## Project

Portfolio/resume artifact demonstrating real production agent engineering, not a toy demo. 5-week plan started 2026-05-14. The eval methodology, observability, and safety story are deliberately part of the deliverable — visibility and rigor signals matter as much as the code.

**Target resume bullet:** 87% faithfulness, 4.2× recall over single-agent baseline, 30-task eval harness, deployed on Modal with prompt-injection defenses.

## Architecture — Planner → Worker → Critic

- **Planner** (Claude Sonnet 4.6): decomposes the question into a DAG of SubTasks.
- **Workers** (Claude Haiku 4.5): parallel ReAct loops, one per SubTask, with tools.
- **Critic** (Claude Sonnet 4.6): claim-level faithfulness + citation verification; can trigger retries (cap = 2 per subtask).
- **Synthesizer**: emits the final Markdown `ResearchReport`.

**Tools exposed to agents:** `web_search` (Tavily), `arxiv_search`, `fetch_url` (httpx + trafilatura), `code_exec` (E2B / Modal sandbox), `cite_lookup`.

## Stack

Python 3.11+, FastAPI + SSE, Pydantic v2, asyncio + httpx, anthropic SDK (primary), OpenTelemetry → Honeycomb/Jaeger, structlog, W&B for eval tracking, Postgres for trace store, Redis for cache + rate limiting, Docker, deploy on Modal or Fly.io. Use `uv` for env management, `ruff` for lint/format, `mypy --strict` for types, `pytest` + `pytest-asyncio` for tests.

**Avoid:** LangChain, LlamaIndex, or other heavy frameworks — framework lock-in is an explicit non-goal.

## Module & file layout

```
agentic-ra/
├── pyproject.toml
├── uv.lock
├── README.md
├── CLAUDE.md
├── .env.example
├── Dockerfile
├── docker-compose.yml          # postgres + redis for local dev
├── Makefile                    # dev / test / eval / deploy targets
├── .github/workflows/
│   ├── ci.yml                  # lint, type, unit, integration
│   └── eval.yml                # run eval harness on PR, comment deltas
├── src/agentic_ra/
│   ├── config.py               # Pydantic Settings, env loading
│   ├── logging.py              # structlog config, OTel bridge
│   ├── tracing.py              # OTel setup, span helpers
│   ├── api/
│   │   ├── app.py              # FastAPI app, lifespan, middleware
│   │   ├── routes.py           # POST /research, SSE stream
│   │   ├── deps.py             # DI: llm client, redis, db pool
│   │   └── schemas.py          # request/response models
│   ├── agents/
│   │   ├── base.py             # AgentBase, ReAct loop primitives
│   │   ├── planner.py
│   │   ├── worker.py
│   │   ├── critic.py
│   │   ├── synthesizer.py
│   │   └── prompts/            # Jinja2 / plain-md prompt templates
│   ├── orchestrator/
│   │   ├── dag.py              # SubTask DAG, topo order
│   │   ├── executor.py         # asyncio runner, parallel siblings, retries
│   │   └── state.py            # run state, intermediate results
│   ├── tools/
│   │   ├── base.py             # Tool protocol, registry, allow-list
│   │   ├── web_search.py       # Tavily
│   │   ├── arxiv.py
│   │   ├── fetch_url.py        # httpx + trafilatura
│   │   ├── code_exec.py        # E2B / Modal sandbox
│   │   └── cite_lookup.py
│   ├── safety/
│   │   ├── fencing.py          # <untrusted_source> wrapping
│   │   ├── scanner.py          # heuristic injection scanner
│   │   └── sanitizer.py        # Haiku-based sanitizer
│   ├── llm/
│   │   ├── client.py           # anthropic SDK wrapper
│   │   ├── models.py           # model enums, cost table
│   │   └── retry.py            # tenacity policies
│   ├── store/
│   │   ├── db.py               # asyncpg pool, trace store
│   │   ├── cache.py            # redis client
│   │   └── migrations/         # alembic
│   └── contracts/              # Pydantic boundary types
│       ├── plan.py             # Plan, SubTask
│       ├── worker.py           # WorkerResult, ToolCall, Step
│       ├── critic.py           # Claim, Citation, CriticVerdict
│       └── report.py           # ResearchReport
├── tests/
│   ├── unit/                   # planner, worker, critic, dag, safety
│   └── integration/            # /research endpoint, full pipeline
├── evals/
│   ├── golden/questions.jsonl  # 30 golden Qs + expected facets
│   ├── adversarial/injections.jsonl  # 20 prompt-injection payloads
│   ├── judge/
│   │   ├── prompts/
│   │   └── rubric.md
│   ├── runner.py               # harness + W&B logging
│   └── kappa.py                # human-judge calibration
├── scripts/                    # dev.sh, run_eval.sh, seed_traces.py
└── deploy/
    ├── modal_app.py
    └── fly.toml
```

**Boundary rule:** Every cross-module call passes a Pydantic model from `contracts/`. No `dict[str, Any]` at module seams. No agent reads another agent's prompt-string output directly — only typed results.

**Tool allow-list rule:** Each agent role declares its allowed tools in `agents/<role>.py` and `tools/base.py` enforces it at registration time. The Critic gets zero internet tools.

## Week-by-week plan — tickets and acceptance criteria

### Week 1 (2026-05-14 →): Single-agent ReAct baseline
**Goal:** End-to-end skeleton — one ReAct agent, two tools, structured output, a real endpoint.

Tickets:
- **T-1.1** Project scaffolding: `uv`, `ruff`, `mypy --strict`, `pre-commit`, `pyproject.toml`, base `Makefile`.
- **T-1.2** `llm/client.py`: anthropic SDK wrapper with tenacity retries (exp backoff + jitter, `max_attempts=4`), cost accounting per call.
- **T-1.3** Tool protocol in `tools/base.py`; implement `web_search` (Tavily) and `arxiv_search`.
- **T-1.4** ReAct loop in `agents/base.py`: think → act → observe, `max_steps=8`, structured stop condition.
- **T-1.5** `contracts/report.py`: `ResearchReport` Pydantic model; force JSON-mode final output.
- **T-1.6** FastAPI POST `/research` returning SSE stream of intermediate thoughts + final report.
- **T-1.7** `logging.py`: structlog + `request_id` context var propagation.
- **T-1.8** Smoke tests against 5 hand-picked questions.

Acceptance: `/research` returns a valid `ResearchReport` for 5 smoke questions; ReAct loop hard-caps at `max_steps`; every citation has URL + snippet; p50 cost per query < $0.15; `mypy --strict` and `ruff check` clean.

### Week 2: Multi-agent orchestration
**Goal:** Planner → parallel Workers → Critic → Synthesizer, wired through a DAG.

Tickets:
- **T-2.1** `contracts/plan.py`: `SubTask`, `Plan` with dependency edges + validation (acyclic).
- **T-2.2** `agents/planner.py` + prompt template; emits a validated `Plan`.
- **T-2.3** `orchestrator/dag.py` + `executor.py`: topo-sort, `asyncio.gather` for siblings, per-task timeout.
- **T-2.4** Refactor `agents/worker.py` to take a `SubTask` and return `WorkerResult`.
- **T-2.5** `agents/critic.py`: claim extraction + per-claim citation verification; emits `CriticVerdict`.
- **T-2.6** Retry policy: on `CriticVerdict.failed_claims`, re-run worker with critic feedback injected; cap = 2 per subtask.
- **T-2.7** `agents/synthesizer.py`: merges verified `WorkerResult`s into final `ResearchReport`.
- **T-2.8** Integration test across 10 questions covering single-hop, multi-hop, and "recent news" categories.

Acceptance: full Planner→Worker→Critic→Synthesizer path runs end-to-end on 10 questions; parallel siblings actually run concurrently (verifiable from span timing); Critic catches ≥1 fabricated claim in a synthetic eval; retry cap is honored.

### Week 3: Eval harness
**Goal:** Quantified rigor — calibrated LLM-judge, baseline-vs-multi deltas, CI eval.

Tickets:
- **T-3.1** `evals/golden/questions.jsonl`: 30 questions across 6 categories (factual, multi-hop, recent, controversial, technical, math/code), each with expected facets.
- **T-3.2** `evals/judge/rubric.md`: dimensions — faithfulness, recall, citation correctness, conciseness; with anchors.
- **T-3.3** Judge prompt + JSON-mode parser; runs as a separate Sonnet 4.6 call.
- **T-3.4** Human labels: spreadsheet of 30 Qs × 2 systems (single-agent baseline + multi-agent), 4 dimensions each.
- **T-3.5** `evals/kappa.py`: compute Cohen's kappa per dimension; iterate judge prompt until kappa ≥ 0.7 on each.
- **T-3.6** `evals/runner.py`: parallel eval, W&B logging — per-Q scores, aggregate, cost, latency.
- **T-3.7** `eval.yml` CI workflow: runs subset (≤10 Qs) on every PR, posts delta vs main as PR comment.
- **T-3.8** Baseline-vs-multi comparison report committed to `docs/eval_report.md`.

Acceptance: judge ↔ human kappa ≥ 0.7 on all four dimensions; CI eval runs on every PR; W&B dashboard shows faithfulness, recall, latency, cost per run; comparison report shows the headline numbers (faithfulness Δ, recall ×).

### Week 4: Harden
**Goal:** Production-grade reliability and safety.

Tickets:
- **T-4.1** Tenacity policies on every external call (LLM, web_search, arxiv, fetch_url) with per-tool tuned `max_attempts` and backoff.
- **T-4.2** Circuit breaker (pybreaker) wrapping each tool: opens after 5 consecutive failures, half-opens after 30s.
- **T-4.3** Redis-backed rate limiter middleware: per-IP + per-API-key budgets.
- **T-4.4** OTel SDK setup; instrument FastAPI, httpx, asyncpg, anthropic SDK; export to Honeycomb or local Jaeger.
- **T-4.5** Span attributes: `agent.role`, `subtask.id`, `tool.name`, `llm.model`, `tokens.in/out`, `cost.usd`.
- **T-4.6** `safety/fencing.py`: wrap every fetched content block in `<untrusted_source>` before it enters a prompt.
- **T-4.7** `safety/scanner.py` (heuristic regex/keyword) + `safety/sanitizer.py` (Haiku fallback for flagged content).
- **T-4.8** `evals/adversarial/injections.jsonl`: 20 payloads across categories — direct override, persona hijack, tool exfiltration, citation spoofing, recursive injection.
- **T-4.9** Adversarial CI test: 20/20 must be blocked; runs on every PR.

Acceptance: traces visible in Jaeger from `/research` down to individual tool calls with cost attribution; rate limiter rejects bursts cleanly; 20/20 adversarial payloads blocked in CI.

### Week 5: Ship
**Goal:** Public artifact others can run and read about.

Tickets:
- **T-5.1** Multi-stage Dockerfile with slim runtime image.
- **T-5.2** `docker-compose.yml`: app + postgres + redis for one-command local dev.
- **T-5.3** Modal deploy (`deploy/modal_app.py`) with secrets via Modal's secret manager.
- **T-5.4** Minimal frontend (HTMX preferred for simplicity, Next.js if more polish is wanted): one page, submits question, streams thoughts + final report.
- **T-5.5** README: architecture diagram, eval results table, quickstart, deploy steps, screenshots.
- **T-5.6** Blog post draft in `docs/blog.md`: design choices, eval methodology, numbers, what surprised you, what you'd do differently.
- **T-5.7** GitHub repo polish: description, topics, public eval dashboard link.

Acceptance: `docker compose up` works on a clean machine; public deploy URL responds to a sample question with a valid streamed `ResearchReport`; README links to live demo, eval dashboard, and blog post.

## Prompt-injection defense (key safety design)

1. **Content fencing** — untrusted content wrapped in `<untrusted_source>` tags.
2. **Structured-output-only final answers** — no free text from fetched pages can become an instruction.
3. **Tool allow-list per agent role** — the Critic has no internet tools.
4. **Heuristic scanner + Haiku sanitizer** for flagged content.
5. **Adversarial CI suite** — 20 payloads, must 100% block.

## Working preferences

- After finishing each stage, explain clearly on what is done in order to teach the user of this project to prepare user for interview
- Production-grade rigor over shortcuts: tests, types, traces, structured logs.
- Tech-stack decisions above are settled. Don't relitigate without a specific reason.
- Favor small, well-typed modules with Pydantic contracts at every agent boundary.
- When suggesting work, anchor to the week and ticket ID above.
