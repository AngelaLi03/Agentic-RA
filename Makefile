.PHONY: install dev lint type test smoke check eval deploy clean

install:
	uv sync --extra dev

dev:
	uv run uvicorn agentic_ra.api.app:app --reload

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

type:
	uv run mypy src

test:
	uv run pytest -q -m "not smoke"

smoke:
	RUN_SMOKE=1 uv run pytest -q tests/integration -m smoke -s

check: lint type test

eval:
	@echo "eval harness lands in Week 3 (evals/runner.py)"

deploy:
	@echo "deploy target lands in Week 5 (deploy/modal_app.py)"

clean:
	find . -path ./.venv -prune -o -name __pycache__ -type d -print -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache
