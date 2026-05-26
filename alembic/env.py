"""Alembic 実行環境（app.database の engine / Base.metadata を利用）。"""

from __future__ import annotations

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

from app import models  # noqa: F401 — メタデータ登録
from app.database import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

_root = Path(__file__).resolve().parent.parent
_sql_override = os.environ.get("MEASUREOS_SQLITE_URL", "").strip()
if _sql_override:
    _url = (
        _sql_override
        if _sql_override.startswith("sqlite:")
        else f"sqlite:///{Path(_sql_override).expanduser().resolve().as_posix()}"
    )
else:
    _db = (_root / "measure_os.db").resolve()
    _url = f"sqlite:///{_db.as_posix()}"

config.set_main_option("sqlalchemy.url", _url)


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
