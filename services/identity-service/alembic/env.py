"""Alembic migration environment for the identity-service (async engine).

Reads ``DATABASE_URL`` from the environment (falling back to the local
docker-compose development database) and runs migrations through the
async SQLAlchemy engine.
"""

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Make `app` (service code) and `shared` (repo-root libraries) importable both
# locally (repo checkout) and in the service container (everything under /app).
SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_DIR))
_repo_root = SERVICE_DIR.parent.parent
if (_repo_root / "shared").is_dir():
    sys.path.insert(0, str(_repo_root))

from app.db import Base  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

DEFAULT_URL = "postgresql+asyncpg://adhera:adhera_dev_password@localhost:5432/identity"
config.set_main_option("sqlalchemy.url", os.environ.get("DATABASE_URL", DEFAULT_URL))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a live connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations against the live database via the async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
