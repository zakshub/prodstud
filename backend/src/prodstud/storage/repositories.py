"""Repository layer abstracting SQL persistence for Production Studio entities."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from prodstud.domain.enums import ErrorCategory, JobStatus, MediaType, ReferenceRole
from prodstud.domain.models import (
    ApprovalQuote,
    AuditEventRecord,
    CredentialSummary,
    GeneratedAssetRecord,
    GenerationJobRecord,
    ProductionPlanRecord,
    ProductionTemplateRecord,
    ProjectRecord,
    QualityReviewRecord,
    ReferenceAssetRecord,
    RevisionRecord,
    UserProfile,
)
from prodstud.security import redact_secrets
from prodstud.storage.database import Database, utc_day_str, utcnow_iso


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:14]}"


class Repository:
    """Unified persistence repository with clean SQL boundaries (SQLite MVP -> PostgreSQL Enterprise ready)."""

    def __init__(self, db: Database):
        self.db = db

    # ── Audit Events (Append-Only, Automatically Secret-Redacted) ──────────
    def record_audit(
        self,
        *,
        user_id: str | None,
        project_id: str | None,
        event_type: str,
        entity_type: str,
        entity_id: str,
        payload: dict[str, Any],
    ) -> AuditEventRecord:
        eid = _new_id("aud")
        now = utcnow_iso()
        safe_payload = redact_secrets(payload)
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO audit_events
                   (id, user_id, project_id, event_type, entity_type, entity_id, payload_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (eid, user_id, project_id, event_type, entity_type, entity_id, json.dumps(safe_payload, sort_keys=True), now),
            )
        return AuditEventRecord(
            id=eid,
            user_id=user_id,
            project_id=project_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=safe_payload,
            created_at=now,
        )

    def list_audit_events(self, user_id: str, project_id: str | None = None, limit: int = 100) -> list[AuditEventRecord]:
        conn = self.db.connect()
        try:
            if project_id:
                rows = conn.execute(
                    """SELECT * FROM audit_events WHERE user_id = ? AND project_id = ?
                       ORDER BY created_at DESC LIMIT ?""",
                    (user_id, project_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM audit_events WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                    (user_id, limit),
                ).fetchall()
            return [
                AuditEventRecord(
                    id=r["id"],
                    user_id=r["user_id"],
                    project_id=r["project_id"],
                    event_type=r["event_type"],
                    entity_type=r["entity_type"],
                    entity_id=r["entity_id"],
                    payload=json.loads(r["payload_json"]),
                    created_at=r["created_at"],
                )
                for r in rows
            ]
        finally:
            conn.close()

    # ── Users & Sessions ───────────────────────────────────────────────────
    def create_user(
        self,
        *,
        email: str,
        display_name: str,
        password_hash: str,
        daily_spend_cap_usd: float = 0.0,
    ) -> UserProfile:
        uid = _new_id("usr")
        now = utcnow_iso()
        norm_email = email.strip().lower()
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO users (id, email, display_name, password_hash, daily_spend_cap_usd, preferred_theme, created_at)
                   VALUES (?, ?, ?, ?, ?, 'dark', ?)""",
                (uid, norm_email, display_name.strip(), password_hash, max(0.0, float(daily_spend_cap_usd)), now),
            )
        return UserProfile(
            id=uid,
            email=norm_email,
            display_name=display_name.strip(),
            daily_spend_cap_usd=max(0.0, float(daily_spend_cap_usd)),
            spent_today_usd=0.0,
            preferred_theme="dark",
            created_at=now,
        )

    def get_user_row_by_email(self, email: str) -> dict[str, Any] | None:
        conn = self.db.connect()
        try:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_user_profile(self, user_id: str) -> UserProfile | None:
        conn = self.db.connect()
        try:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if not row:
                return None
            spent = self.get_user_spent_today(user_id)
            return UserProfile(
                id=row["id"],
                email=row["email"],
                display_name=row["display_name"],
                daily_spend_cap_usd=float(row["daily_spend_cap_usd"]),
                spent_today_usd=spent,
                preferred_theme=row["preferred_theme"],
                created_at=row["created_at"],
            )
        finally:
            conn.close()

    def update_user_settings(
        self,
        user_id: str,
        *,
        display_name: str | None = None,
        daily_spend_cap_usd: float | None = None,
        preferred_theme: str | None = None,
    ) -> UserProfile:
        with self.db.transaction() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if not row:
                raise KeyError("User not found")
            new_name = display_name.strip() if display_name is not None else row["display_name"]
            new_cap = max(0.0, float(daily_spend_cap_usd)) if daily_spend_cap_usd is not None else float(row["daily_spend_cap_usd"])
            new_theme = preferred_theme if preferred_theme in {"dark", "light"} else row["preferred_theme"]
            conn.execute(
                "UPDATE users SET display_name = ?, daily_spend_cap_usd = ?, preferred_theme = ? WHERE id = ?",
                (new_name, new_cap, new_theme, user_id),
            )
        profile = self.get_user_profile(user_id)
        assert profile is not None
        return profile

    def create_session(self, user_id: str, token_hash: str, ttl_hours: int = 72) -> None:
        now = datetime.now(timezone.utc)
        expires = (now + timedelta(hours=ttl_hours)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (token_hash, user_id, utcnow_iso(), expires),
            )

    def get_user_id_for_session(self, token_hash: str) -> str | None:
        conn = self.db.connect()
        try:
            row = conn.execute("SELECT user_id, expires_at FROM sessions WHERE token_hash = ?", (token_hash,)).fetchone()
            if not row:
                return None
            if row["expires_at"] <= utcnow_iso():
                return None
            return str(row["user_id"])
        finally:
            conn.close()

    def delete_session(self, token_hash: str) -> None:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))

    # ── Provider Credentials (Server-Side Encrypted Vault) ─────────────────
    def upsert_credential(
        self,
        *,
        user_id: str,
        provider: str,
        encrypted_key: str,
        masked_key: str,
        validation_note: str | None = None,
        validated_at: str | None = None,
    ) -> CredentialSummary:
        now = utcnow_iso()
        cid = _new_id("cred")
        with self.db.transaction() as conn:
            existing = conn.execute(
                "SELECT id FROM provider_credentials WHERE user_id = ? AND provider = ?",
                (user_id, provider),
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE provider_credentials
                       SET encrypted_key = ?, masked_key = ?, status = 'active',
                           validated_at = ?, validation_note = ?, updated_at = ?
                       WHERE id = ?""",
                    (encrypted_key, masked_key, validated_at, validation_note, now, existing["id"]),
                )
            else:
                conn.execute(
                    """INSERT INTO provider_credentials
                       (id, user_id, provider, encrypted_key, masked_key, status, validated_at, validation_note, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)""",
                    (cid, user_id, provider, encrypted_key, masked_key, validated_at, validation_note, now, now),
                )
        return CredentialSummary(
            provider=provider,
            masked_key=masked_key,
            status="active",
            validated_at=validated_at,
            validation_note=validation_note,
            updated_at=now,
        )

    def get_credential_row(self, user_id: str, provider: str) -> dict[str, Any] | None:
        conn = self.db.connect()
        try:
            row = conn.execute(
                "SELECT * FROM provider_credentials WHERE user_id = ? AND provider = ?",
                (user_id, provider),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_credentials(self, user_id: str) -> list[CredentialSummary]:
        conn = self.db.connect()
        try:
            rows = conn.execute(
                "SELECT provider, masked_key, status, validated_at, validation_note, updated_at FROM provider_credentials WHERE user_id = ? ORDER BY provider",
                (user_id,),
            ).fetchall()
            return [CredentialSummary(**dict(r)) for r in rows]
        finally:
            conn.close()

    def revoke_credential(self, user_id: str, provider: str) -> bool:
        now = utcnow_iso()
        with self.db.transaction() as conn:
            cur = conn.execute(
                """UPDATE provider_credentials
                   SET status = 'revoked', encrypted_key = '', masked_key = 'revoked',
                       validation_note = 'Revoked by user', updated_at = ?
                   WHERE user_id = ? AND provider = ?""",
                (now, user_id, provider),
            )
            return cur.rowcount > 0

    def update_credential_validation(self, user_id: str, provider: str, validated_at: str, note: str) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """UPDATE provider_credentials
                   SET validated_at = ?, validation_note = ?, updated_at = ?
                   WHERE user_id = ? AND provider = ?""",
                (validated_at, note, utcnow_iso(), user_id, provider),
            )

    # ── Spend Telemetry ────────────────────────────────────────────────────
    def get_user_spent_today(self, user_id: str) -> float:
        conn = self.db.connect()
        try:
            row = conn.execute(
                "SELECT COALESCE(SUM(reported_cost_usd), 0.0) AS total FROM spend_telemetry WHERE user_id = ? AND recorded_day = ?",
                (user_id, utc_day_str()),
            ).fetchone()
            return round(float(row["total"]) if row else 0.0, 6)
        finally:
            conn.close()

    def record_spend(
        self,
        *,
        user_id: str,
        job_id: str,
        provider_id: str,
        model_id: str,
        estimated_cost_usd: float,
        reported_cost_usd: float,
    ) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO spend_telemetry
                   (id, user_id, job_id, provider_id, model_id, estimated_cost_usd, reported_cost_usd, recorded_day, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    _new_id("spd"),
                    user_id,
                    job_id,
                    provider_id,
                    model_id,
                    round(float(estimated_cost_usd), 6),
                    round(float(reported_cost_usd), 6),
                    utc_day_str(),
                    utcnow_iso(),
                ),
            )

    # ── Projects ───────────────────────────────────────────────────────────
    def create_project(self, user_id: str, name: str, description: str = "") -> ProjectRecord:
        pid = _new_id("prj")
        now = utcnow_iso()
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO projects (id, user_id, name, description, archived, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 0, ?, ?)""",
                (pid, user_id, name.strip(), description.strip(), now, now),
            )
        return ProjectRecord(
            id=pid,
            user_id=user_id,
            name=name.strip(),
            description=description.strip(),
            archived=False,
            created_at=now,
            updated_at=now,
            asset_count=0,
            latest_asset_id=None,
        )

    def list_projects(self, user_id: str, include_archived: bool = False) -> list[ProjectRecord]:
        conn = self.db.connect()
        try:
            sql = """
                SELECT p.*,
                       (SELECT COUNT(*) FROM generated_assets a WHERE a.project_id = p.id) AS asset_count,
                       (SELECT a.id FROM generated_assets a WHERE a.project_id = p.id ORDER BY a.created_at DESC LIMIT 1) AS latest_asset_id
                FROM projects p
                WHERE p.user_id = ?
            """
            params: list[Any] = [user_id]
            if not include_archived:
                sql += " AND p.archived = 0"
            sql += " ORDER BY p.updated_at DESC"
            rows = conn.execute(sql, params).fetchall()
            return [
                ProjectRecord(
                    id=r["id"],
                    user_id=r["user_id"],
                    name=r["name"],
                    description=r["description"],
                    archived=bool(r["archived"]),
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                    asset_count=int(r["asset_count"]),
                    latest_asset_id=r["latest_asset_id"],
                )
                for r in rows
            ]
        finally:
            conn.close()

    def get_project(self, user_id: str, project_id: str) -> ProjectRecord | None:
        conn = self.db.connect()
        try:
            row = conn.execute(
                """SELECT p.*,
                          (SELECT COUNT(*) FROM generated_assets a WHERE a.project_id = p.id) AS asset_count,
                          (SELECT a.id FROM generated_assets a WHERE a.project_id = p.id ORDER BY a.created_at DESC LIMIT 1) AS latest_asset_id
                   FROM projects p WHERE p.id = ? AND p.user_id = ?""",
                (project_id, user_id),
            ).fetchone()
            if not row:
                return None
            return ProjectRecord(
                id=row["id"],
                user_id=row["user_id"],
                name=row["name"],
                description=row["description"],
                archived=bool(row["archived"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                asset_count=int(row["asset_count"]),
                latest_asset_id=row["latest_asset_id"],
            )
        finally:
            conn.close()

    def update_project(
        self,
        user_id: str,
        project_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        archived: bool | None = None,
    ) -> ProjectRecord | None:
        existing = self.get_project(user_id, project_id)
        if not existing:
            return None
        new_name = name.strip() if name is not None else existing.name
        new_desc = description.strip() if description is not None else existing.description
        new_arch = 1 if (archived if archived is not None else existing.archived) else 0
        now = utcnow_iso()
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE projects SET name = ?, description = ?, archived = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                (new_name, new_desc, new_arch, now, project_id, user_id),
            )
        return self.get_project(user_id, project_id)

    def touch_project(self, project_id: str) -> None:
        with self.db.transaction() as conn:
            conn.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (utcnow_iso(), project_id))

    # ── Reference Assets ───────────────────────────────────────────────────
    def create_reference(
        self,
        *,
        project_id: str,
        user_id: str,
        filename: str,
        storage_relpath: str,
        mime_type: str,
        size_bytes: int,
        sha256: str,
        width: int | None,
        height: int | None,
        role: ReferenceRole,
        rights_confirmed: bool,
        notes: str = "",
    ) -> ReferenceAssetRecord:
        rid = _new_id("ref")
        now = utcnow_iso()
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO reference_assets
                   (id, project_id, user_id, filename, storage_relpath, mime_type, size_bytes, sha256, width, height, role, rights_confirmed, notes, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    rid,
                    project_id,
                    user_id,
                    filename,
                    storage_relpath,
                    mime_type,
                    size_bytes,
                    sha256,
                    width,
                    height,
                    role.value,
                    1 if rights_confirmed else 0,
                    notes.strip(),
                    now,
                ),
            )
        self.touch_project(project_id)
        return ReferenceAssetRecord(
            id=rid,
            project_id=project_id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            sha256=sha256,
            width=width,
            height=height,
            role=role,
            rights_confirmed=rights_confirmed,
            notes=notes.strip(),
            created_at=now,
        )

    def list_references(self, user_id: str, project_id: str) -> list[ReferenceAssetRecord]:
        conn = self.db.connect()
        try:
            rows = conn.execute(
                "SELECT * FROM reference_assets WHERE user_id = ? AND project_id = ? ORDER BY created_at DESC",
                (user_id, project_id),
            ).fetchall()
            return [self._row_to_reference(r) for r in rows]
        finally:
            conn.close()

    def get_reference_rows(self, user_id: str, project_id: str, ref_ids: list[str]) -> list[dict[str, Any]]:
        if not ref_ids:
            return []
        placeholders = ",".join("?" for _ in ref_ids)
        conn = self.db.connect()
        try:
            rows = conn.execute(
                f"SELECT * FROM reference_assets WHERE user_id = ? AND project_id = ? AND id IN ({placeholders})",
                [user_id, project_id, *ref_ids],
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_reference_row(self, user_id: str, reference_id: str) -> dict[str, Any] | None:
        conn = self.db.connect()
        try:
            row = conn.execute(
                "SELECT * FROM reference_assets WHERE user_id = ? AND id = ?",
                (user_id, reference_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def _row_to_reference(r: sqlite3.Row | dict[str, Any]) -> ReferenceAssetRecord:
        return ReferenceAssetRecord(
            id=r["id"],
            project_id=r["project_id"],
            filename=r["filename"],
            mime_type=r["mime_type"],
            size_bytes=int(r["size_bytes"]),
            sha256=r["sha256"],
            width=r["width"],
            height=r["height"],
            role=ReferenceRole(r["role"]),
            rights_confirmed=bool(r["rights_confirmed"]),
            notes=r["notes"],
            created_at=r["created_at"],
        )

    # ── Briefs & Production Plans ──────────────────────────────────────────
    def save_brief(self, user_id: str, project_id: str, media_type: MediaType, prompt_text: str, payload: dict[str, Any]) -> str:
        bid = _new_id("brf")
        now = utcnow_iso()
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO production_briefs (id, project_id, user_id, media_type, prompt_text, payload_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (bid, project_id, user_id, media_type.value, prompt_text, json.dumps(payload, sort_keys=True), now),
            )
        return bid

    def get_brief_payload(self, user_id: str, brief_id: str) -> dict[str, Any] | None:
        conn = self.db.connect()
        try:
            row = conn.execute(
                "SELECT payload_json FROM production_briefs WHERE id = ? AND user_id = ?",
                (brief_id, user_id),
            ).fetchone()
            return json.loads(row["payload_json"]) if row else None
        finally:
            conn.close()

    def save_plan(self, user_id: str, plan: ProductionPlanRecord) -> ProductionPlanRecord:
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO production_plans
                   (id, project_id, user_id, brief_id, parent_plan_id, version, media_type, task_mode, plan_json, approved_for_generation, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    plan.id,
                    plan.project_id,
                    user_id,
                    plan.brief_id,
                    plan.parent_plan_id,
                    plan.version,
                    plan.media_type.value,
                    plan.task_mode.value,
                    plan.model_dump_json(),
                    1 if plan.approved_for_generation else 0,
                    plan.created_at,
                    plan.updated_at,
                ),
            )
        self.touch_project(plan.project_id)
        return plan

    def update_plan(self, user_id: str, plan: ProductionPlanRecord) -> ProductionPlanRecord:
        plan.updated_at = utcnow_iso()
        with self.db.transaction() as conn:
            conn.execute(
                """UPDATE production_plans
                   SET plan_json = ?, approved_for_generation = ?, updated_at = ?
                   WHERE id = ? AND user_id = ?""",
                (
                    plan.model_dump_json(),
                    1 if plan.approved_for_generation else 0,
                    plan.updated_at,
                    plan.id,
                    user_id,
                ),
            )
        self.touch_project(plan.project_id)
        return plan

    def get_plan(self, user_id: str, plan_id: str) -> ProductionPlanRecord | None:
        conn = self.db.connect()
        try:
            row = conn.execute(
                "SELECT plan_json FROM production_plans WHERE id = ? AND user_id = ?",
                (plan_id, user_id),
            ).fetchone()
            return ProductionPlanRecord.model_validate_json(row["plan_json"]) if row else None
        finally:
            conn.close()

    def list_plans(self, user_id: str, project_id: str) -> list[ProductionPlanRecord]:
        conn = self.db.connect()
        try:
            rows = conn.execute(
                "SELECT plan_json FROM production_plans WHERE user_id = ? AND project_id = ? ORDER BY created_at DESC",
                (user_id, project_id),
            ).fetchall()
            return [ProductionPlanRecord.model_validate_json(r["plan_json"]) for r in rows]
        finally:
            conn.close()

    # ── Approval Quotes ────────────────────────────────────────────────────
    def save_quote(self, user_id: str, quote: ApprovalQuote) -> ApprovalQuote:
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO approval_quotes
                   (quote_id, user_id, plan_id, provider_id, model_id, quote_json, confirmation_token, consumed, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
                (
                    quote.quote_id,
                    user_id,
                    quote.plan_id,
                    quote.provider_id,
                    quote.model_id,
                    quote.model_dump_json(),
                    quote.confirmation_token,
                    utcnow_iso(),
                    quote.expires_at,
                ),
            )
        return quote

    def get_quote_row(self, user_id: str, quote_id: str) -> dict[str, Any] | None:
        conn = self.db.connect()
        try:
            row = conn.execute(
                "SELECT * FROM approval_quotes WHERE quote_id = ? AND user_id = ?",
                (quote_id, user_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def mark_quote_consumed(self, quote_id: str) -> None:
        with self.db.transaction() as conn:
            conn.execute("UPDATE approval_quotes SET consumed = 1 WHERE quote_id = ?", (quote_id,))

    # ── Generation Jobs ────────────────────────────────────────────────────
    def create_job(self, user_id: str, job: GenerationJobRecord) -> GenerationJobRecord:
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO generation_jobs
                   (id, project_id, user_id, plan_id, provider_id, model_id, media_type, status, idempotency_key,
                    is_billable, is_local_test_fixture, estimated_cost_usd, provider_job_id, asset_id,
                    error_category, error_message, provider_may_have_accepted, diagnostics_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job.id,
                    job.project_id,
                    user_id,
                    job.plan_id,
                    job.provider_id,
                    job.model_id,
                    job.media_type.value,
                    job.status.value,
                    job.idempotency_key,
                    1 if job.is_billable else 0,
                    1 if job.is_local_test_fixture else 0,
                    job.estimated_cost_usd,
                    job.provider_job_id,
                    job.asset_id,
                    job.error_category.value if job.error_category else None,
                    job.error_message,
                    1 if job.provider_may_have_accepted else 0,
                    json.dumps(redact_secrets(job.diagnostics), sort_keys=True),
                    job.created_at,
                    job.updated_at,
                ),
            )
        return job

    def update_job(
        self,
        job_id: str,
        *,
        status: JobStatus | None = None,
        provider_job_id: str | None = None,
        asset_id: str | None = None,
        error_category: ErrorCategory | None = None,
        error_message: str | None = None,
        provider_may_have_accepted: bool | None = None,
        diagnostics: dict[str, Any] | None = None,
    ) -> GenerationJobRecord:
        now = utcnow_iso()
        with self.db.transaction() as conn:
            row = conn.execute("SELECT * FROM generation_jobs WHERE id = ?", (job_id,)).fetchone()
            if not row:
                raise KeyError(f"Job not found: {job_id}")
            new_status = status.value if status is not None else row["status"]
            new_pjid = provider_job_id if provider_job_id is not None else row["provider_job_id"]
            new_aid = asset_id if asset_id is not None else row["asset_id"]
            new_ecat = error_category.value if error_category is not None else row["error_category"]
            new_emsg = redact_secrets(error_message) if error_message is not None else row["error_message"]
            new_may = (
                (1 if provider_may_have_accepted else 0)
                if provider_may_have_accepted is not None
                else row["provider_may_have_accepted"]
            )
            cur_diag = json.loads(row["diagnostics_json"])
            if diagnostics:
                cur_diag.update(redact_secrets(diagnostics))
            conn.execute(
                """UPDATE generation_jobs
                   SET status = ?, provider_job_id = ?, asset_id = ?, error_category = ?, error_message = ?,
                       provider_may_have_accepted = ?, diagnostics_json = ?, updated_at = ?
                   WHERE id = ?""",
                (new_status, new_pjid, new_aid, new_ecat, new_emsg, new_may, json.dumps(cur_diag, sort_keys=True), now, job_id),
            )
            updated = conn.execute("SELECT * FROM generation_jobs WHERE id = ?", (job_id,)).fetchone()
            assert updated is not None
            return self._row_to_job(updated)

    def get_job(self, user_id: str, job_id: str) -> GenerationJobRecord | None:
        conn = self.db.connect()
        try:
            row = conn.execute("SELECT * FROM generation_jobs WHERE id = ? AND user_id = ?", (job_id, user_id)).fetchone()
            return self._row_to_job(row) if row else None
        finally:
            conn.close()

    def get_job_by_idempotency(self, user_id: str, idempotency_key: str) -> GenerationJobRecord | None:
        conn = self.db.connect()
        try:
            row = conn.execute(
                "SELECT * FROM generation_jobs WHERE user_id = ? AND idempotency_key = ?",
                (user_id, idempotency_key),
            ).fetchone()
            return self._row_to_job(row) if row else None
        finally:
            conn.close()

    def list_jobs(self, user_id: str, project_id: str | None = None) -> list[GenerationJobRecord]:
        conn = self.db.connect()
        try:
            if project_id:
                rows = conn.execute(
                    "SELECT * FROM generation_jobs WHERE user_id = ? AND project_id = ? ORDER BY created_at DESC",
                    (user_id, project_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM generation_jobs WHERE user_id = ? ORDER BY created_at DESC LIMIT 100",
                    (user_id,),
                ).fetchall()
            return [self._row_to_job(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def _row_to_job(r: Any) -> GenerationJobRecord:
        return GenerationJobRecord(
            id=r["id"],
            project_id=r["project_id"],
            plan_id=r["plan_id"],
            provider_id=r["provider_id"],
            model_id=r["model_id"],
            media_type=MediaType(r["media_type"]),
            status=JobStatus(r["status"]),
            idempotency_key=r["idempotency_key"],
            is_billable=bool(r["is_billable"]),
            is_local_test_fixture=bool(r["is_local_test_fixture"]),
            estimated_cost_usd=r["estimated_cost_usd"],
            provider_job_id=r["provider_job_id"],
            asset_id=r["asset_id"],
            error_category=ErrorCategory(r["error_category"]) if r["error_category"] else None,
            error_message=r["error_message"],
            provider_may_have_accepted=bool(r["provider_may_have_accepted"]),
            diagnostics=json.loads(r["diagnostics_json"]),
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )

    # ── Generated Assets ───────────────────────────────────────────────────
    def create_asset(
        self,
        *,
        user_id: str,
        project_id: str,
        plan_id: str,
        job_id: str,
        parent_asset_id: str | None,
        version_number: int,
        media_type: MediaType,
        provider_id: str,
        model_id: str,
        is_local_test_fixture: bool,
        filename: str,
        storage_relpath: str,
        mime_type: str,
        size_bytes: int,
        sha256: str,
        width: int | None,
        height: int | None,
        duration_s: float | None,
        fps: float | None,
        metadata: dict[str, Any],
    ) -> GeneratedAssetRecord:
        aid = _new_id("ast")
        now = utcnow_iso()
        safe_meta = redact_secrets(metadata)
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO generated_assets
                   (id, project_id, user_id, plan_id, job_id, parent_asset_id, version_number, media_type,
                    provider_id, model_id, is_local_test_fixture, filename, storage_relpath, mime_type,
                    size_bytes, sha256, width, height, duration_s, fps, tags_json, collection_name,
                    is_favorite, accepted, metadata_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', NULL, 0, 0, ?, ?)""",
                (
                    aid,
                    project_id,
                    user_id,
                    plan_id,
                    job_id,
                    parent_asset_id,
                    version_number,
                    media_type.value,
                    provider_id,
                    model_id,
                    1 if is_local_test_fixture else 0,
                    filename,
                    storage_relpath,
                    mime_type,
                    size_bytes,
                    sha256,
                    width,
                    height,
                    duration_s,
                    fps,
                    json.dumps(safe_meta, sort_keys=True),
                    now,
                ),
            )
        self.touch_project(project_id)
        return GeneratedAssetRecord(
            id=aid,
            project_id=project_id,
            plan_id=plan_id,
            job_id=job_id,
            parent_asset_id=parent_asset_id,
            version_number=version_number,
            media_type=media_type,
            provider_id=provider_id,
            model_id=model_id,
            is_local_test_fixture=is_local_test_fixture,
            filename=filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            sha256=sha256,
            width=width,
            height=height,
            duration_s=duration_s,
            fps=fps,
            tags=[],
            collection_name=None,
            is_favorite=False,
            accepted=False,
            metadata=safe_meta,
            created_at=now,
        )

    def get_asset_row(self, user_id: str, asset_id: str) -> dict[str, Any] | None:
        conn = self.db.connect()
        try:
            row = conn.execute("SELECT * FROM generated_assets WHERE id = ? AND user_id = ?", (asset_id, user_id)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_asset(self, user_id: str, asset_id: str) -> GeneratedAssetRecord | None:
        row = self.get_asset_row(user_id, asset_id)
        return self._row_to_asset(row) if row else None

    def list_assets(
        self,
        user_id: str,
        *,
        project_id: str | None = None,
        media_type: MediaType | None = None,
        tag: str | None = None,
        collection_name: str | None = None,
        favorite_only: bool = False,
        query: str | None = None,
    ) -> list[GeneratedAssetRecord]:
        conn = self.db.connect()
        try:
            sql = "SELECT * FROM generated_assets WHERE user_id = ?"
            params: list[Any] = [user_id]
            if project_id:
                sql += " AND project_id = ?"
                params.append(project_id)
            if media_type:
                sql += " AND media_type = ?"
                params.append(media_type.value)
            if collection_name:
                sql += " AND collection_name = ?"
                params.append(collection_name)
            if favorite_only:
                sql += " AND is_favorite = 1"
            sql += " ORDER BY created_at DESC"
            rows = conn.execute(sql, params).fetchall()
            assets = [self._row_to_asset(r) for r in rows]
            if tag:
                tag_l = tag.strip().lower()
                assets = [a for a in assets if any(t.lower() == tag_l for t in a.tags)]
            if query and query.strip():
                q = query.strip().lower()
                assets = [
                    a
                    for a in assets
                    if q in a.filename.lower()
                    or q in (a.collection_name or "").lower()
                    or q in json.dumps(a.metadata).lower()
                    or any(q in t.lower() for t in a.tags)
                ]
            return assets
        finally:
            conn.close()

    def update_asset_organization(
        self,
        user_id: str,
        asset_id: str,
        *,
        tags: list[str] | None = None,
        collection_name: str | None = None,
        is_favorite: bool | None = None,
        accepted: bool | None = None,
    ) -> GeneratedAssetRecord | None:
        row = self.get_asset_row(user_id, asset_id)
        if not row:
            return None
        new_tags = sorted({t.strip() for t in tags if t.strip()}) if tags is not None else json.loads(row["tags_json"])
        new_col = collection_name.strip() if isinstance(collection_name, str) and collection_name.strip() else (None if collection_name == "" else row["collection_name"])
        new_fav = (1 if is_favorite else 0) if is_favorite is not None else row["is_favorite"]
        new_acc = (1 if accepted else 0) if accepted is not None else row["accepted"]
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE generated_assets SET tags_json = ?, collection_name = ?, is_favorite = ?, accepted = ? WHERE id = ? AND user_id = ?",
                (json.dumps(new_tags), new_col, new_fav, new_acc, asset_id, user_id),
            )
        return self.get_asset(user_id, asset_id)

    def next_version_number(self, project_id: str, media_type: MediaType) -> int:
        conn = self.db.connect()
        try:
            row = conn.execute(
                "SELECT COALESCE(MAX(version_number), 0) AS mx FROM generated_assets WHERE project_id = ? AND media_type = ?",
                (project_id, media_type.value),
            ).fetchone()
            return int(row["mx"]) + 1 if row else 1
        finally:
            conn.close()

    @staticmethod
    def _row_to_asset(r: Any) -> GeneratedAssetRecord:
        return GeneratedAssetRecord(
            id=r["id"],
            project_id=r["project_id"],
            plan_id=r["plan_id"],
            job_id=r["job_id"],
            parent_asset_id=r["parent_asset_id"],
            version_number=int(r["version_number"]),
            media_type=MediaType(r["media_type"]),
            provider_id=r["provider_id"],
            model_id=r["model_id"],
            is_local_test_fixture=bool(r["is_local_test_fixture"]),
            filename=r["filename"],
            mime_type=r["mime_type"],
            size_bytes=int(r["size_bytes"]),
            sha256=r["sha256"],
            width=r["width"],
            height=r["height"],
            duration_s=r["duration_s"],
            fps=r["fps"],
            tags=json.loads(r["tags_json"]),
            collection_name=r["collection_name"],
            is_favorite=bool(r["is_favorite"]),
            accepted=bool(r["accepted"]),
            metadata=json.loads(r["metadata_json"]),
            created_at=r["created_at"],
        )

    # ── Quality Reviews ────────────────────────────────────────────────────
    def save_quality_review(self, user_id: str, review: QualityReviewRecord) -> QualityReviewRecord:
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO quality_reviews (id, asset_id, plan_id, user_id, media_type, review_json, human_feedback_status, human_feedback_note, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    review.id,
                    review.asset_id,
                    review.plan_id,
                    user_id,
                    review.media_type.value,
                    review.model_dump_json(),
                    review.human_feedback_status,
                    review.human_feedback_note,
                    review.created_at,
                ),
            )
        return review

    def get_latest_review(self, user_id: str, asset_id: str) -> QualityReviewRecord | None:
        conn = self.db.connect()
        try:
            row = conn.execute(
                "SELECT review_json, human_feedback_status, human_feedback_note FROM quality_reviews WHERE user_id = ? AND asset_id = ? ORDER BY created_at DESC LIMIT 1",
                (user_id, asset_id),
            ).fetchone()
            if not row:
                return None
            rec = QualityReviewRecord.model_validate_json(row["review_json"])
            rec.human_feedback_status = row["human_feedback_status"]
            rec.human_feedback_note = row["human_feedback_note"]
            return rec
        finally:
            conn.close()

    def record_human_feedback(self, user_id: str, review_id: str, status: str, note: str) -> QualityReviewRecord | None:
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT review_json FROM quality_reviews WHERE id = ? AND user_id = ?",
                (review_id, user_id),
            ).fetchone()
            if not row:
                return None
            rec = QualityReviewRecord.model_validate_json(row["review_json"])
            rec.human_feedback_status = status
            rec.human_feedback_note = note.strip()
            conn.execute(
                "UPDATE quality_reviews SET review_json = ?, human_feedback_status = ?, human_feedback_note = ? WHERE id = ? AND user_id = ?",
                (rec.model_dump_json(), status, note.strip(), review_id, user_id),
            )
            return rec

    # ── Revisions ──────────────────────────────────────────────────────────
    def save_revision(self, user_id: str, rev: RevisionRecord) -> RevisionRecord:
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO revisions
                   (id, project_id, user_id, source_plan_id, new_plan_id, source_asset_id, change_request,
                    changed_fields_json, preserved_fields_json, provider_regeneration_note, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    rev.id,
                    rev.project_id,
                    user_id,
                    rev.source_plan_id,
                    rev.new_plan_id,
                    rev.source_asset_id,
                    rev.change_request,
                    json.dumps(rev.changed_fields),
                    json.dumps(rev.preserved_fields),
                    rev.provider_regeneration_note,
                    rev.created_at,
                ),
            )
        return rev

    def list_revisions(self, user_id: str, project_id: str) -> list[RevisionRecord]:
        conn = self.db.connect()
        try:
            rows = conn.execute(
                "SELECT * FROM revisions WHERE user_id = ? AND project_id = ? ORDER BY created_at DESC",
                (user_id, project_id),
            ).fetchall()
            return [
                RevisionRecord(
                    id=r["id"],
                    project_id=r["project_id"],
                    source_plan_id=r["source_plan_id"],
                    new_plan_id=r["new_plan_id"],
                    source_asset_id=r["source_asset_id"],
                    change_request=r["change_request"],
                    changed_fields=json.loads(r["changed_fields_json"]),
                    preserved_fields=json.loads(r["preserved_fields_json"]),
                    provider_regeneration_note=r["provider_regeneration_note"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]
        finally:
            conn.close()

    # ── Production Templates (V1 Foundation) ───────────────────────────────
    def create_template(
        self,
        *,
        user_id: str,
        name: str,
        media_type: MediaType,
        description: str,
        default_brief: dict[str, Any],
    ) -> ProductionTemplateRecord:
        tid = _new_id("tpl")
        now = utcnow_iso()
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO production_templates (id, user_id, name, media_type, description, default_brief_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (tid, user_id, name.strip(), media_type.value, description.strip(), json.dumps(default_brief, sort_keys=True), now),
            )
        return ProductionTemplateRecord(
            id=tid,
            user_id=user_id,
            name=name.strip(),
            media_type=media_type,
            description=description.strip(),
            default_brief=default_brief,
            created_at=now,
        )

    def list_templates(self, user_id: str) -> list[ProductionTemplateRecord]:
        conn = self.db.connect()
        try:
            rows = conn.execute(
                "SELECT * FROM production_templates WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
            return [
                ProductionTemplateRecord(
                    id=r["id"],
                    user_id=r["user_id"],
                    name=r["name"],
                    media_type=MediaType(r["media_type"]),
                    description=r["description"],
                    default_brief=json.loads(r["default_brief_json"]),
                    created_at=r["created_at"],
                )
                for r in rows
            ]
        finally:
            conn.close()
