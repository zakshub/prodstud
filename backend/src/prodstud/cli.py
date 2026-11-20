"""Level 1 Interface: Production Studio CLI (Operational & API-Parity Foundation).

Drives the full production workflow directly from the command line without GUI dependency:
init-db, audit-db, snapshot, capabilities, register, project, plan, generate, job, review, revise, export, serve.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import uvicorn

from prodstud.config import Settings
from prodstud.domain.enums import MediaType
from prodstud.domain.models import BriefInput, RevisionRequest
from prodstud.engine.revision_engine import apply_targeted_revision
from prodstud.providers.base import ProviderAdapterError
from prodstud.runtime import AppRuntime
from prodstud.security import hash_password


def _emit(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False))


def _resolve_user(rt: AppRuntime, email: str):
    row = rt.repo.get_user_row_by_email(email)
    if not row:
        raise SystemExit(f"User not found: {email}. Register first via `prodstud register`.")
    user = rt.repo.get_user_profile(row["id"])
    assert user is not None
    return user


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prodstud", description="Production Studio CLI (Level 1 Operational Interface)")
    parser.add_argument("--data-dir", default=None, help="Override private runtime data directory")
    parser.add_argument("--env", default=None, choices=["development", "test", "production"], help="Override runtime env")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="Initialize SQLite database and verify integrity")
    sub.add_parser("audit-db", help="Run PRAGMA integrity_check and report registry/DB status")
    sub.add_parser("snapshot", help="Create atomic verified SQLite backup snapshot with SHA-256 manifest")

    cap_p = sub.add_parser("capabilities", help="List verified provider capabilities")
    cap_p.add_argument("--media-type", choices=["image", "video"], default=None)

    reg_p = sub.add_parser("register", help="Create a single-user account")
    reg_p.add_argument("--email", required=True)
    reg_p.add_argument("--name", required=True)
    reg_p.add_argument("--password", required=True)

    prj_p = sub.add_parser("project", help="Manage production projects")
    prj_sub = prj_p.add_subparsers(dest="project_cmd", required=True)
    prj_create = prj_sub.add_parser("create")
    prj_create.add_argument("--email", required=True)
    prj_create.add_argument("--name", required=True)
    prj_create.add_argument("--description", default="")
    prj_list = prj_sub.add_parser("list")
    prj_list.add_argument("--email", required=True)

    plan_p = sub.add_parser("plan", help="Create an Image or timed Video Production Plan")
    plan_p.add_argument("--email", required=True)
    plan_p.add_argument("--project-id", required=True)
    plan_p.add_argument("--media-type", required=True, choices=["image", "video"])
    plan_p.add_argument("--prompt", required=True)
    plan_p.add_argument("--aspect-ratio", default=None)
    plan_p.add_argument("--resolution", default=None)
    plan_p.add_argument("--duration", type=float, default=None)
    plan_p.add_argument("--provider", default=None)
    plan_p.add_argument("--model", default=None)

    gen_p = sub.add_parser("generate", help="Request quote and explicitly approve generation")
    gen_p.add_argument("--email", required=True)
    gen_p.add_argument("--plan-id", required=True)
    gen_p.add_argument("--provider", default=None)
    gen_p.add_argument("--model", default=None)
    gen_p.add_argument("--approve", action="store_true", help="Explicitly confirm execution after inspecting quote")

    rev_p = sub.add_parser("revise", help="Apply a controlled targeted revision preserving unaffected decisions")
    rev_p.add_argument("--email", required=True)
    rev_p.add_argument("--plan-id", required=True)
    rev_p.add_argument("--change", required=True)
    rev_p.add_argument("--shot", type=int, default=None)

    exp_p = sub.add_parser("export", help="Export generated asset + sanitized provenance sidecar to ZIP")
    exp_p.add_argument("--email", required=True)
    exp_p.add_argument("--asset-id", required=True)
    exp_p.add_argument("--out", required=True)

    srv_p = sub.add_parser("serve", help="Run Production Studio HTTP API & Web UI server")
    srv_p.add_argument("--host", default="127.0.0.1")
    srv_p.add_argument("--port", type=int, default=8000)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = Settings.from_env(data_dir_override=args.data_dir, env_override=args.env)
    rt = AppRuntime.create(settings)

    if args.command == "init-db":
        _emit({"status": "initialized", "db_path": str(settings.db_path), "integrity": rt.db.verify_integrity()})
        return 0

    if args.command == "audit-db":
        _emit(
            {
                "integrity": rt.db.verify_integrity(),
                "protocols_loaded": len(rt.protocols.entries),
                "registry_version": rt.protocols.version,
                "storage_usage_bytes": rt.store.total_usage_bytes(),
                "environment": settings.env,
            }
        )
        return 0

    if args.command == "snapshot":
        _emit(rt.db.create_atomic_snapshot(settings.snapshots_dir))
        return 0

    if args.command == "capabilities":
        mt = MediaType(args.media_type) if args.media_type else None
        _emit([c.model_dump() for c in rt.providers.list_capabilities(mt)])
        return 0

    if args.command == "register":
        if rt.repo.get_user_row_by_email(args.email):
            print(f"Error: user already exists: {args.email}", file=sys.stderr)
            return 1
        user = rt.repo.create_user(
            email=args.email,
            display_name=args.name,
            password_hash=hash_password(args.password),
            daily_spend_cap_usd=settings.default_daily_spend_cap_usd,
        )
        _emit(user.model_dump())
        return 0

    if args.command == "project":
        user = _resolve_user(rt, args.email)
        if args.project_cmd == "create":
            prj = rt.repo.create_project(user.id, args.name, args.description)
            _emit(prj.model_dump())
            return 0
        if args.project_cmd == "list":
            _emit([p.model_dump() for p in rt.repo.list_projects(user.id)])
            return 0

    if args.command == "plan":
        user = _resolve_user(rt, args.email)
        mt = MediaType(args.media_type)
        brief = BriefInput(
            project_id=args.project_id,
            media_type=mt,
            prompt_text=args.prompt,
            aspect_ratio=args.aspect_ratio,
            resolution=args.resolution,
            duration_s=args.duration,
            provider_id=args.provider,
            model_id=args.model,
        )
        cap = rt.providers.resolve_capability(mt, args.provider, args.model)
        bid = rt.repo.save_brief(user.id, args.project_id, mt, brief.prompt_text, brief.model_dump())
        plan = rt.engine.create_plan(brief_id=bid, brief=brief, references=[], capability=cap)
        rt.repo.save_plan(user.id, plan)
        _emit(plan.model_dump())
        return 0

    if args.command == "generate":
        user = _resolve_user(rt, args.email)
        plan = rt.repo.get_plan(user.id, args.plan_id)
        if not plan:
            print(f"Error: plan not found: {args.plan_id}", file=sys.stderr)
            return 1
        quote = rt.jobs.request_quote(user=user, plan=plan, provider_id=args.provider, model_id=args.model)
        if not args.approve:
            _emit({"status": "awaiting_explicit_approval", "quote": quote.model_dump(), "next": "Re-run with --approve after verifying quote"})
            return 0
        try:
            job, asset, review = rt.jobs.submit_approved_job(
                user=user,
                plan=plan,
                quote_id=quote.quote_id,
                confirmation_token=quote.confirmation_token,
                explicit_user_confirmed=True,
            )
            _emit(
                {
                    "job": job.model_dump(),
                    "asset": asset.model_dump() if asset else None,
                    "quality_review": review.model_dump() if review else None,
                }
            )
            return 0
        except ProviderAdapterError as exc:
            print(f"Blocked [{exc.category.value}]: {exc}", file=sys.stderr)
            return 2

    if args.command == "revise":
        user = _resolve_user(rt, args.email)
        plan = rt.repo.get_plan(user.id, args.plan_id)
        if not plan:
            print(f"Error: plan not found: {args.plan_id}", file=sys.stderr)
            return 1
        cap = rt.providers.resolve_capability(plan.media_type, plan.recommended_provider, plan.recommended_model)
        new_plan, rev = apply_targeted_revision(
            source_plan=plan,
            revision_request=RevisionRequest(change_request=args.change, target_shot_order=args.shot),
            source_asset_id=None,
            capability=cap,
        )
        rt.repo.save_plan(user.id, new_plan)
        rt.repo.save_revision(user.id, rev)
        _emit({"plan": new_plan.model_dump(), "revision": rev.model_dump()})
        return 0

    if args.command == "export":
        from prodstud.api.routes_production import _build_sanitized_sidecar

        user = _resolve_user(rt, args.email)
        row = rt.repo.get_asset_row(user.id, args.asset_id)
        if not row:
            print(f"Error: asset not found: {args.asset_id}", file=sys.stderr)
            return 1
        sidecar = _build_sanitized_sidecar(rt, user.id, row)
        zip_bytes = rt.store.build_export_zip([(row["storage_relpath"], row["filename"], sidecar)])
        out_path = Path(args.out).resolve()
        out_path.write_bytes(zip_bytes)
        _emit({"status": "exported", "path": str(out_path), "size_bytes": len(zip_bytes)})
        return 0

    if args.command == "serve":
        from prodstud.api.app import create_app

        uvicorn.run(create_app(settings), host=args.host, port=args.port)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
