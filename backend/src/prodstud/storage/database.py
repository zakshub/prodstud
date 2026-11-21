"""SQLite persistence with WAL mode, startup PRAGMA integrity_check, migrations, and atomic snapshots."""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    daily_spend_cap_usd REAL NOT NULL DEFAULT 0.0,
    preferred_theme TEXT NOT NULL DEFAULT 'dark',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS provider_credentials (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    encrypted_key TEXT NOT NULL,
    masked_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    validated_at TEXT,
    validation_note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, provider)
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    archived INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reference_assets (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    storage_relpath TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    width INTEGER,
    height INTEGER,
    role TEXT NOT NULL DEFAULT 'style',
    rights_confirmed INTEGER NOT NULL DEFAULT 1,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS production_briefs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    media_type TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS production_plans (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    brief_id TEXT NOT NULL REFERENCES production_briefs(id) ON DELETE CASCADE,
    parent_plan_id TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    media_type TEXT NOT NULL,
    task_mode TEXT NOT NULL,
    plan_json TEXT NOT NULL,
    approved_for_generation INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approval_quotes (
    quote_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id TEXT NOT NULL REFERENCES production_plans(id) ON DELETE CASCADE,
    provider_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    quote_json TEXT NOT NULL,
    confirmation_token TEXT NOT NULL,
    consumed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS generation_jobs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id TEXT NOT NULL REFERENCES production_plans(id) ON DELETE CASCADE,
    provider_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    media_type TEXT NOT NULL,
    status TEXT NOT NULL,
    idempotency_key TEXT UNIQUE NOT NULL,
    is_billable INTEGER NOT NULL DEFAULT 0,
    is_local_test_fixture INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd REAL,
    provider_job_id TEXT,
    asset_id TEXT,
    error_category TEXT,
    error_message TEXT,
    provider_may_have_accepted INTEGER NOT NULL DEFAULT 0,
    diagnostics_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS generated_assets (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id TEXT NOT NULL REFERENCES production_plans(id) ON DELETE CASCADE,
    job_id TEXT NOT NULL REFERENCES generation_jobs(id) ON DELETE CASCADE,
    parent_asset_id TEXT,
    version_number INTEGER NOT NULL DEFAULT 1,
    media_type TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    is_local_test_fixture INTEGER NOT NULL DEFAULT 0,
    filename TEXT NOT NULL,
    storage_relpath TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    width INTEGER,
    height INTEGER,
    duration_s REAL,
    fps REAL,
    tags_json TEXT NOT NULL DEFAULT '[]',
    collection_name TEXT,
    is_favorite INTEGER NOT NULL DEFAULT 0,
    accepted INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quality_reviews (
    id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL REFERENCES generated_assets(id) ON DELETE CASCADE,
    plan_id TEXT NOT NULL REFERENCES production_plans(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    media_type TEXT NOT NULL,
    review_json TEXT NOT NULL,
    human_feedback_status TEXT,
    human_feedback_note TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS revisions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_plan_id TEXT NOT NULL,
    new_plan_id TEXT NOT NULL,
    source_asset_id TEXT,
    change_request TEXT NOT NULL,
    changed_fields_json TEXT NOT NULL,
    preserved_fields_json TEXT NOT NULL,
    provider_regeneration_note TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS spend_telemetry (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_id TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    estimated_cost_usd REAL NOT NULL DEFAULT 0.0,
    reported_cost_usd REAL NOT NULL DEFAULT 0.0,
    recorded_day TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS production_templates (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    media_type TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    default_brief_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    project_id TEXT,
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS batch_quotes (
    batch_quote_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    quote_json TEXT NOT NULL,
    confirmation_token TEXT NOT NULL,
    consumed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS generation_batches (
    batch_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    batch_quote_id TEXT NOT NULL,
    status TEXT NOT NULL,
    record_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vision_qc_quotes (
    quote_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    asset_id TEXT NOT NULL REFERENCES generated_assets(id) ON DELETE CASCADE,
    quote_json TEXT NOT NULL,
    confirmation_token TEXT NOT NULL,
    consumed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_projects_user ON projects(user_id, archived, updated_at);
CREATE INDEX IF NOT EXISTS idx_plans_project ON production_plans(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_project ON generation_jobs(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_assets_project ON generated_assets(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_spend_user_day ON spend_telemetry(user_id, recorded_day);
CREATE INDEX IF NOT EXISTS idx_audit_project ON audit_events(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_batches_project ON generation_batches(project_id, created_at);
"""


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utc_day_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class DatabaseCorruptionError(RuntimeError):
    """Raised when SQLite fails fail-closed startup integrity verification."""


class Database:
    """Thread-safe SQLite database wrapper with WAL mode, integrity verification, and atomic snapshots."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_and_verify()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def verify_integrity(self) -> str:
        conn = self.connect()
        try:
            row = conn.execute("PRAGMA integrity_check;").fetchone()
            result = str(row[0]) if row else "unknown"
            if result.lower() != "ok":
                raise DatabaseCorruptionError(f"SQLite integrity_check failed: {result}")
            return result
        finally:
            conn.close()

    def _init_and_verify(self) -> None:
        if self.db_path.exists() and self.db_path.stat().st_size > 0:
            self.verify_integrity()
        with self.transaction() as conn:
            conn.executescript(SCHEMA_SQL)
            existing = conn.execute("SELECT version FROM schema_migrations WHERE version = 1").fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                    (1, utcnow_iso()),
                )
        self.verify_integrity()

    def create_atomic_snapshot(self, snapshots_dir: Path) -> dict[str, str]:
        """Create an atomic verified backup snapshot with companion SHA-256 manifest."""
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = snapshots_dir / f"prodstud_snapshot_{stamp}.sqlite3"
        tmp = snapshots_dir / f"prodstud_snapshot_{stamp}.sqlite3.tmp"

        src = self.connect()
        dst = sqlite3.connect(str(tmp))
        try:
            src.backup(dst)
            check = dst.execute("PRAGMA integrity_check;").fetchone()
            if not check or str(check[0]).lower() != "ok":
                raise DatabaseCorruptionError("Snapshot integrity check failed.")
        finally:
            dst.close()
            src.close()

        tmp.replace(target)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        manifest = target.with_suffix(".sqlite3.sha256")
        manifest_tmp = target.with_suffix(".sqlite3.sha256.tmp")
        manifest_tmp.write_text(f"{digest}  {target.name}\n", encoding="utf-8")
        manifest_tmp.replace(manifest)

        return {
            "snapshot_path": str(target),
            "manifest_path": str(manifest),
            "sha256": digest,
            "integrity": "ok",
        }
