.PHONY: help install up down test test-unit test-integration lint format typecheck check run-api

help:
	@echo "Available commands:"
	@echo "  make install           Install dependencies using uv"
	@echo "  make up                Start Docker services (PostgreSQL)"
	@echo "  make down              Stop Docker services"
	@echo "  make test              Run all tests"
	@echo "  make test-unit         Run unit tests"
	@echo "  make test-integration  Run integration tests"
	@echo "  make lint              Run ruff linter and format check"
	@echo "  make format            Run ruff code formatting and autofix"
	@echo "  make typecheck         Run mypy static type analysis"
	@echo "  make check             Run lint, typecheck, and tests"
	@echo "  make run-api           Run FastAPI development server"

install:
	uv sync

up:
	docker compose up -d

down:
	docker compose down

test:
	uv run pytest

test-unit:
	uv run pytest tests/unit

test-integration:
	uv run pytest tests/integration

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	uv run mypy app

check: lint typecheck test

run-api:
	uv run uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
