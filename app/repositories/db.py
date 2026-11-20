"""
SetuHaul Logistics — Database Repository
Provides safe, parameterized, connection-managed data access over SQLite.
Enforces explicit transactions and foreign keys.
"""

import os
import sqlite3
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

DEFAULT_DB_PATH = os.getenv("DATABASE_PATH", "setuhaul_freight_operations.db")


class DatabaseRepository:
    def __init__(self, db_path: str = DEFAULT_DB_PATH, timeout: float = 5.0):
        self.db_path = db_path
        self.timeout = timeout

    @contextmanager
    def get_connection(self):
        """Context manager yielding a SQLite connection with foreign keys enabled."""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
        finally:
            conn.close()

    def fetch_all(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Execute a read query and return all rows as dictionaries."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Execute a read query and return the first row as a dictionary, or None."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None

    def execute_write(self, query: str, params: tuple = ()) -> int:
        """Execute a single write query inside an auto-committed transaction."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount

    @contextmanager
    def immediate_transaction(self):
        """
        Yields an open cursor within a BEGIN IMMEDIATE transaction.
        Acquires SQLite's reserved lock immediately, preventing write races.
        Rolls back on error, commits on normal exit.
        """
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("BEGIN IMMEDIATE;")
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
