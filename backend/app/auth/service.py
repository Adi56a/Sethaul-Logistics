"""
SetuHaul Logistics — Authentication Service
Manages user accounts, password hashing, session tokens, and pre-seeded demo accounts.
"""
import os
import time
import uuid
import hashlib
import sqlite3
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

from app.auth.models import (
    UserRole,
    UserProfile,
    LoginRequest,
    SignupRequest,
    AuthResponse
)
from app.repositories.db import resolve_db_path


class AuthService:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or resolve_db_path()
        self._tokens: Dict[str, UserProfile] = {}
        self._init_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _hash_password(self, password: str, salt: str) -> str:
        """Secure PBKDF2 HMAC SHA-256 hash."""
        return hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            100000
        ).hex()

    def _init_db(self):
        """Initialize users table and populate demo accounts with default password '123456'."""
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    driver_id TEXT,
                    shipment_id TEXT,
                    order_reference TEXT,
                    phone TEXT,
                    carrier_id TEXT,
                    created_at TEXT NOT NULL
                );
            """)

            # Ensure all columns exist for existing installations
            cols = [col[1] for col in conn.execute("PRAGMA table_info(users);").fetchall()]
            for col_name in ["driver_id", "shipment_id", "order_reference", "phone", "carrier_id"]:
                if col_name not in cols:
                    conn.execute(f"ALTER TABLE users ADD COLUMN {col_name} TEXT;")

            # Seed demo accounts if empty or update their passwords
            row = conn.execute("SELECT COUNT(*) AS cnt FROM users;").fetchone()
            if row["cnt"] == 0:
                demo_accounts = [
                    {
                        "user_id": "USR-ADMIN-01",
                        "username": "admin",
                        "full_name": "Neha Bansal (Operations Supervisor)",
                        "role": "ADMIN",
                        "driver_id": None,
                        "shipment_id": None,
                        "order_reference": None,
                        "phone": "+91-9810011001",
                        "carrier_id": None
                    },
                    {
                        "user_id": "USR-ADMIN-02",
                        "username": "ops",
                        "full_name": "Warehouse Operations Dispatcher",
                        "role": "ADMIN",
                        "driver_id": None,
                        "shipment_id": None,
                        "order_reference": None,
                        "phone": "+91-9810011002",
                        "carrier_id": None
                    },
                    {
                        "user_id": "USR-DRV006",
                        "username": "DRV006",
                        "full_name": "Manoj Sharma",
                        "role": "DRIVER",
                        "driver_id": "DRV006",
                        "shipment_id": "SHP1006",
                        "order_reference": "ORD-260804-006",
                        "phone": "+91-9000010006",
                        "carrier_id": "CAR003"
                    },
                    {
                        "user_id": "USR-DRV004",
                        "username": "DRV004",
                        "full_name": "Sandeep Meena",
                        "role": "DRIVER",
                        "driver_id": "DRV004",
                        "shipment_id": "SHP1004",
                        "order_reference": "ORD-260804-004",
                        "phone": "+91-9000010004",
                        "carrier_id": "CAR002"
                    },
                    {
                        "user_id": "USR-DRV015",
                        "username": "DRV015",
                        "full_name": "Mohammed Salim",
                        "role": "DRIVER",
                        "driver_id": "DRV015",
                        "shipment_id": "SHP1015",
                        "order_reference": "ORD-260804-015",
                        "phone": "+91-9000010015",
                        "carrier_id": "CAR004"
                    },
                    {
                        "user_id": "USR-DRV007",
                        "username": "DRV007",
                        "full_name": "Nitin Patil",
                        "role": "DRIVER",
                        "driver_id": "DRV007",
                        "shipment_id": "SHP1016",
                        "order_reference": "ORD-260804-016",
                        "phone": "+91-9000010007",
                        "carrier_id": "CAR003"
                    },
                    {
                        "user_id": "USR-DRV012",
                        "username": "DRV012",
                        "full_name": "Arjun Das",
                        "role": "DRIVER",
                        "driver_id": "DRV012",
                        "shipment_id": "SHP1012",
                        "order_reference": "ORD-260804-012",
                        "phone": "+91-9000010012",
                        "carrier_id": "CAR002"
                    },
                    {
                        "user_id": "USR-DRV003",
                        "username": "DRV003",
                        "full_name": "Mukesh Yadav",
                        "role": "DRIVER",
                        "driver_id": "DRV003",
                        "shipment_id": "SHP1003",
                        "order_reference": "ORD-260804-003",
                        "phone": "+91-9000010003",
                        "carrier_id": "CAR001"
                    }
                ]

                salt = "setuhaul_static_salt_2026"
                default_hash = self._hash_password("123456", salt)
                now = time.strftime("%Y-%m-%d %H:%M:%S")

                for acc in demo_accounts:
                    conn.execute("""
                        INSERT INTO users (
                            user_id, username, password_hash, salt, full_name, role,
                            driver_id, shipment_id, order_reference, phone, carrier_id, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (
                        acc["user_id"],
                        acc["username"],
                        default_hash,
                        salt,
                        acc["full_name"],
                        acc["role"],
                        acc["driver_id"],
                        acc["shipment_id"],
                        acc["order_reference"],
                        acc["phone"],
                        acc["carrier_id"],
                        now
                    ))

    def authenticate(self, req: LoginRequest) -> Optional[AuthResponse]:
        """Verify username & password; return AuthResponse with bearer token if valid."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE LOWER(username) = LOWER(?);",
                (req.username.strip(),)
            ).fetchone()

            if not row:
                return None

            expected_hash = self._hash_password(req.password, row["salt"])
            if expected_hash != row["password_hash"]:
                return None

            keys = row.keys()
            user = UserProfile(
                user_id=row["user_id"],
                username=row["username"],
                full_name=row["full_name"],
                role=UserRole(row["role"]),
                driver_id=row["driver_id"] if "driver_id" in keys else None,
                shipment_id=row["shipment_id"] if "shipment_id" in keys else None,
                order_reference=row["order_reference"] if "order_reference" in keys else None,
                phone=row["phone"] if "phone" in keys else None,
                carrier_id=row["carrier_id"] if "carrier_id" in keys else None,
                created_at=row["created_at"] if "created_at" in keys else None
            )

            token = f"sth_{uuid.uuid4().hex}"
            self._tokens[token] = user

            return AuthResponse(
                status="SUCCESS",
                access_token=token,
                token_type="bearer",
                user=user,
                message=f"Welcome back, {user.full_name}!"
            )

    def register(self, req: SignupRequest) -> AuthResponse:
        """Register a new user account."""
        with self._conn() as conn:
            # Check for existing username
            existing = conn.execute(
                "SELECT user_id FROM users WHERE LOWER(username) = LOWER(?);",
                (req.username.strip(),)
            ).fetchone()

            if existing:
                raise ValueError(f"Username '{req.username}' is already taken.")

            user_id = f"USR-{uuid.uuid4().hex[:8].upper()}"
            salt = uuid.uuid4().hex[:16]
            pwd_hash = self._hash_password(req.password, salt)
            now = time.strftime("%Y-%m-%d %H:%M:%S")

            conn.execute("""
                INSERT INTO users (
                    user_id, username, password_hash, salt, full_name, role,
                    driver_id, shipment_id, order_reference, phone, carrier_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                user_id,
                req.username.strip(),
                pwd_hash,
                salt,
                req.full_name.strip(),
                req.role.value,
                req.driver_id,
                None,
                None,
                req.phone,
                None,
                now
            ))

            user = UserProfile(
                user_id=user_id,
                username=req.username.strip(),
                full_name=req.full_name.strip(),
                role=req.role,
                driver_id=req.driver_id,
                phone=req.phone,
                created_at=now
            )

            token = f"sth_{uuid.uuid4().hex}"
            self._tokens[token] = user

            return AuthResponse(
                status="SUCCESS",
                access_token=token,
                token_type="bearer",
                user=user,
                message="Account registered successfully."
            )

    def authenticate_token(self, token: str) -> Optional[UserProfile]:
        """Validate bearer token and return user profile."""
        if not token:
            return None
        return self._tokens.get(token)


# Global singleton instance
auth_service = AuthService()
