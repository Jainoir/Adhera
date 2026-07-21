#!/bin/sh
# Run pending database migrations, then start the service.
set -e

alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
