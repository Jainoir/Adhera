.PHONY: up down build test lint typecheck fmt

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

test:
	pytest

lint:
	ruff check .
	ruff format --check .

fmt:
	ruff check --fix .
	ruff format .

typecheck:
	mypy services shared
