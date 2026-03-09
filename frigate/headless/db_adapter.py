import json
import os
import sqlite3
import time
from dataclasses import dataclass
from typing import Any

from frigate.const import CONFIG_DIR


class DatabaseAdapter:
    def append_audit(self, stream: str, entry: dict[str, Any]) -> None:
        raise NotImplementedError

    def list_audit(self, stream: str, limit: int = 100) -> list[dict[str, Any]]:
        raise NotImplementedError


@dataclass
class SqliteAdapter(DatabaseAdapter):
    path: str = f"{CONFIG_DIR}/headless_runtime.db"

    def __post_init__(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS headless_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stream TEXT NOT NULL,
                    ts INTEGER NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def append_audit(self, stream: str, entry: dict[str, Any]) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT INTO headless_audit(stream, ts, payload) VALUES(?, ?, ?)",
                (stream, int(time.time()), json.dumps(entry, separators=(",", ":"))),
            )
            conn.commit()

    def list_audit(self, stream: str, limit: int = 100) -> list[dict[str, Any]]:
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(
                """
                SELECT payload
                FROM headless_audit
                WHERE stream = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (stream, max(1, min(1000, int(limit)))),
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            try:
                items.append(json.loads(row[0]))
            except Exception:
                continue
        return items


@dataclass
class MySQLAdapter(SqliteAdapter):
    pass


@dataclass
class PostgresAdapter(SqliteAdapter):
    pass


def build_database_adapter() -> DatabaseAdapter:
    driver = os.getenv("FRIGATE_DB_DRIVER", "sqlite").strip().lower()
    if driver == "mysql":
        return MySQLAdapter(path=os.getenv("FRIGATE_DB_PATH", f"{CONFIG_DIR}/headless_runtime.db"))
    if driver in {"postgres", "postgresql"}:
        return PostgresAdapter(path=os.getenv("FRIGATE_DB_PATH", f"{CONFIG_DIR}/headless_runtime.db"))
    return SqliteAdapter(path=os.getenv("FRIGATE_DB_PATH", f"{CONFIG_DIR}/headless_runtime.db"))
