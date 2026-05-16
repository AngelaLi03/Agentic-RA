# Agentic-RA

Production-grade agentic research assistant. See `CLAUDE.md` for architecture and plan.

## Week 1 — single-agent ReAct baseline

```bash
uv sync --extra dev
cp .env.example .env  # fill in ANTHROPIC_API_KEY, TAVILY_API_KEY
make dev              # uvicorn agentic_ra.api.app:app --reload
```

Then:

```bash
curl -N -X POST http://localhost:8000/research \
  -H 'Content-Type: application/json' \
  -d '{"question": "What recent papers compare ReAct and Reflexion for multi-hop QA?"}'
```

## Quality gates

```bash
make check   # ruff + mypy --strict + unit tests
make smoke    # live 5-question end-to-end (needs real keys + RUN_SMOKE=1)
```
