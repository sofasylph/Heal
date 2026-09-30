.PHONY: setup check-python api api-llm web test lint eval eval-llm up down

PYTHON ?= python3

check-python:
	@$(PYTHON) -c 'import sys; assert sys.version_info >= (3, 11), f"Python 3.11+ required, found {sys.version.split()[0]}. Use: make setup PYTHON=python3.11"' \
		|| (echo "Install Python 3.11+ (Ubuntu: sudo apt install python3 python3-venv)"; exit 1)

setup: check-python
	cd backend && $(PYTHON) -m venv .venv && .venv/bin/pip install -e ".[dev]"
	cd frontend && npm install

api:
	cd backend && .venv/bin/uvicorn claimtrace.api.app:app --reload --port 8000

api-llm:
	cd backend && CLAIMTRACE_LLM_PROVIDER=claude CLAIMTRACE_LLM_CACHE=./llm_cache.jsonl \
		.venv/bin/uvicorn claimtrace.api.app:app --reload --port 8000

web:
	cd frontend && npm run dev

test:
	cd backend && .venv/bin/pytest -q

lint:
	cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .
	cd frontend && npm run lint

eval:
	cd backend && .venv/bin/python -m claimtrace.evaluation.run --n 200 --seed 7 --out ../docs/eval

# Needs Anthropic credentials on first run; cached responses replay afterwards.
eval-llm:
	cd backend && .venv/bin/python -m claimtrace.evaluation.run --n 200 --seed 7 \
		--reasoner claude --cache ../docs/eval/llm_cache.jsonl --out ../docs/eval/llm

up:
	docker compose up --build

down:
	docker compose down
