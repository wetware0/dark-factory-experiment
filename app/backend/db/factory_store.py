"""Factory persistence selector.

The broader DynaChat app still uses Postgres/pgvector. The PAVE factory portal
can use SQL Server, which is the preferred WTG operational database target.
"""

from __future__ import annotations

from types import ModuleType

from backend import config


def _impl() -> ModuleType:
    provider = config.FACTORY_STORAGE_PROVIDER
    if provider in {"sqlserver", "mssql", "sql_server"}:
        from backend.db import factory_sqlserver_repository

        return factory_sqlserver_repository
    if provider in {"postgres", "postgresql"}:
        from backend.db import factory_repository

        return factory_repository
    if provider in {"sqlite", "sqlite3"}:
        from backend.db import factory_sqlite_repository

        return factory_sqlite_repository
    raise RuntimeError(
        "Unsupported FACTORY_STORAGE_PROVIDER. Use 'sqlserver', 'postgres', or 'sqlite'. "
        f"Got {provider!r}."
    )


def __getattr__(name: str):
    return getattr(_impl(), name)
