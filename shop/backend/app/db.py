from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Put DB file in your project folder (shop/minishop.db) regardless of where you run uvicorn from
BASE_DIR = Path(__file__).resolve().parents[2]  # .../shop
DEFAULT_DB_URL = f"sqlite:///{(BASE_DIR / 'minishop.db').as_posix()}"

DATABASE_URL = os.environ.get("MINISHOP_DATABASE_URL", DEFAULT_DB_URL)

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from backend.app.persistence.models import Base

    Base.metadata.create_all(bind=engine)

    # --- Tiny SQLite migration: add users.is_admin if missing ---
    if engine.dialect.name == "sqlite":
        with engine.begin() as conn:
            cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()]
            if cols and "is_admin" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0"
                )

            # Bootstrap: if users exist but none are admin, promote the first user
            cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()]
            if cols and "is_admin" in cols:
                total = conn.exec_driver_sql("SELECT COUNT(*) FROM users").scalar_one()
                admins = conn.exec_driver_sql("SELECT COUNT(*) FROM users WHERE is_admin = 1").scalar_one()

                if total > 0 and admins == 0:
                    conn.exec_driver_sql(
                        "UPDATE users SET is_admin = 1 WHERE id = (SELECT id FROM users ORDER BY rowid LIMIT 1)"
                    )