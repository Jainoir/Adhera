SERVICES := api-gateway identity-service medication-service notification-service
DB_SERVICES := identity-service medication-service notification-service

.PHONY: up down build install lint fmt typecheck test test-integration migrate

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

install:
	pip install -r requirements-dev.txt

lint:
	ruff check .
	ruff format --check .

fmt:
	ruff check --fix .
	ruff format .

# Every service uses the same top-level `app` package name, so mypy and
# pytest must run once per service instead of once for the whole tree.
typecheck:
	mypy shared tests
	@set -e; for svc in $(SERVICES); do echo "==> mypy services/$$svc"; mypy services/$$svc; done

test:
	pytest shared
	@set -e; for svc in $(SERVICES); do echo "==> pytest services/$$svc"; pytest services/$$svc; done

test-integration:
	pytest tests/integration -m integration

migrate:
	@set -e; for svc in $(DB_SERVICES); do echo "==> alembic upgrade head ($$svc)"; (cd services/$$svc && alembic upgrade head); done
