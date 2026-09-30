.PHONY: setup api web test lint eval up down

setup:
	cd backend && python -m venv .venv && .venv/bin/pip install -e ".[dev]"
	cd frontend && npm install

api:
	cd backend && .venv/bin/uvicorn claimtrace.api.app:app --reload --port 8000

web:
	cd frontend && npm run dev

test:
	cd backend && .venv/bin/pytest -q

lint:
	cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .
	cd frontend && npm run lint

eval:
	cd backend && .venv/bin/python -m claimtrace.evaluation.run --n 200 --seed 7 --out ../docs/eval

up:
	docker compose up --build

down:
	docker compose down
