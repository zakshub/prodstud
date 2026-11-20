#!/usr/bin/env python3
"""Controlled Live Google Provider Smoke Test (Image + Video).

Safety Guarantees:
- Default mode is --dry-run ($0.00 spent).
- Reads GEMINI_API_KEY strictly from environment variable (never CLI flags, never logged).
- Displays exact expected cost disclosure BEFORE requesting authorization.
- Refuses any billable request without BOTH --execute-live, --authorize-spend-usd > 0, AND --confirm-billable.
- Keeps user Spend Guard cap at $0.00 unless explicitly authorized.
- Never blindly retries JobStatus.UNKNOWN or uncertain paid submissions.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))

from prodstud.config import Settings
from prodstud.domain.enums import JobStatus, MediaType
from prodstud.domain.models import BriefInput
from prodstud.providers.base import ProviderAdapterError
from prodstud.runtime import AppRuntime
from prodstud.security import hash_password, mask_api_key, redact_secrets

IMAGE_MODEL = "gemini-nano-banana-2.1"
VIDEO_MODEL = "gemini-omni-1.2-flash"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Controlled Live Google Image & Video Smoke Test (Zero-spend default; explicit authorization required)."
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Build plans and signed approval quotes without contacting Google or spending money ($0.00).",
    )
    p.add_argument(
        "--validate-key-only",
        action="store_true",
        default=False,
        help="Perform non-billable GET /v1beta/models metadata check only ($0.00).",
    )
    p.add_argument(
        "--execute-live",
        action="store_true",
        default=False,
        help="Execute 1 Google image + 1 Google video request (requires --authorize-spend-usd and --confirm-billable).",
    )
    p.add_argument(
        "--authorize-spend-usd",
        type=float,
        default=0.0,
        help="Explicit temporary spend cap in USD for this smoke test (default: $0.00).",
    )
    p.add_argument(
        "--confirm-billable",
        action="store_true",
        default=False,
        help="Explicitly confirm authorization to incur real Google API billing charges.",
    )
    p.add_argument(
        "--skip-video",
        action="store_true",
        default=False,
        help="Run only the 1 image request (skip paid-tier video clip).",
    )
    p.add_argument(
        "--poll-timeout-s",
        type=int,
        default=240,
        help="Maximum seconds to poll async Google video job before stopping cleanly.",
    )
    p.add_argument(
        "--output-dir",
        default=None,
        help="Optional directory to store smoke test DB and downloaded real assets (defaults to temp dir).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # Default to dry-run if neither --validate-key-only nor --execute-live was explicitly selected
    dry_run = args.dry_run or (not args.validate_key_only and not args.execute_live)

    api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    has_env_key = bool(api_key)

    tmp_ctx = tempfile.TemporaryDirectory(prefix="prodstud_live_smoke_") if not args.output_dir else None
    data_dir = Path(args.output_dir).resolve() if args.output_dir else Path(tmp_ctx.name)  # type: ignore[union-attr]
    data_dir.mkdir(parents=True, exist_ok=True)

    try:
        settings = Settings.from_env(data_dir_override=str(data_dir), env_override="development")
        rt = AppRuntime.create(settings)

        # Always start user at $0.00 Spend Guard cap!
        user = rt.repo.create_user(
            email="smoke-owner@prodstud.local",
            display_name="Smoke Test Owner",
            password_hash=hash_password("SmokeTestPass!2026"),
            daily_spend_cap_usd=0.0,
        )
        project = rt.repo.create_project(user.id, "Controlled Live Google Verification", "1 image + 1 video smoke test")

        if has_env_key:
            rt.repo.upsert_credential(
                user_id=user.id,
                provider="google",
                encrypted_key=rt.vault.encrypt(api_key),
                masked_key=mask_api_key(api_key),
                validation_note="Loaded from GEMINI_API_KEY env for controlled smoke test",
            )

        # Build 1 Image Plan (1K, 3:2) & 1 Video Plan (4s, 720p, 16:9)
        img_cap = rt.providers.resolve_capability(MediaType.IMAGE, "google_gemini_image", IMAGE_MODEL)
        img_brief = BriefInput(
            project_id=project.id,
            media_type=MediaType.IMAGE,
            prompt_text="Matte ceramic pour-over coffee carafe on pale walnut table, soft morning window light, 50mm realistic editorial still",
            aspect_ratio="3:2",
            resolution="1K",
            provider_id="google_gemini_image",
            model_id=IMAGE_MODEL,
        )
        img_bid = rt.repo.save_brief(user.id, project.id, MediaType.IMAGE, img_brief.prompt_text, img_brief.model_dump())
        img_plan = rt.engine.create_plan(brief_id=img_bid, brief=img_brief, references=[], capability=img_cap)
        rt.repo.save_plan(user.id, img_plan)

        vid_cap = rt.providers.resolve_capability(MediaType.VIDEO, "google_gemini_video", VIDEO_MODEL)
        vid_brief = BriefInput(
            project_id=project.id,
            media_type=MediaType.VIDEO,
            prompt_text="Slow smooth dolly-in on steam rising gently from black ceramic espresso cup on walnut counter, natural morning light",
            aspect_ratio="16:9",
            resolution="720p",
            duration_s=4.0,
            provider_id="google_gemini_video",
            model_id=VIDEO_MODEL,
        )
        vid_bid = rt.repo.save_brief(user.id, project.id, MediaType.VIDEO, vid_brief.prompt_text, vid_brief.model_dump())
        vid_plan = rt.engine.create_plan(brief_id=vid_bid, brief=vid_brief, references=[], capability=vid_cap)
        rt.repo.save_plan(user.id, vid_plan)

        # Quote under $0.00 default cap first to verify Spend Guard disclosure
        img_quote_zero = rt.jobs.request_quote(user=user, plan=img_plan, provider_id="google_gemini_image", model_id=IMAGE_MODEL)
        vid_quote_zero = rt.jobs.request_quote(user=user, plan=vid_plan, provider_id="google_gemini_video", model_id=VIDEO_MODEL)

        report: dict[str, Any] = {
            "mode": "dry_run" if dry_run else ("validate_key_only" if args.validate_key_only else "execute_live"),
            "credential_present_in_env": has_env_key,
            "masked_credential": mask_api_key(api_key) if has_env_key else None,
            "default_spend_cap_usd": user.daily_spend_cap_usd,
            "pre_flight_cost_disclosure": {
                "image": {
                    "provider": "google_gemini_image",
                    "model": IMAGE_MODEL,
                    "settings": img_quote_zero.settings_summary,
                    "estimated_cost_usd": img_quote_zero.estimated_cost_usd,
                    "pricing_disclosure": img_quote_zero.pricing_disclosure,
                    "spend_guard_allows_at_zero_cap": img_quote_zero.spend_guard_allows,
                },
                "video": {
                    "provider": "google_gemini_video",
                    "model": VIDEO_MODEL,
                    "settings": vid_quote_zero.settings_summary,
                    "estimated_cost_usd": vid_quote_zero.estimated_cost_usd,
                    "pricing_disclosure": vid_quote_zero.pricing_disclosure,
                    "spend_guard_allows_at_zero_cap": vid_quote_zero.spend_guard_allows,
                },
            },
            "live_verification_status": "NOT_EXECUTED_DRY_RUN",
            "spend_incurred_usd": 0.0,
        }

        if dry_run:
            if not has_env_key:
                report["remaining_blocker"] = (
                    "GEMINI_API_KEY environment variable is not set. Supply an owner-authorized Google Gemini API key "
                    "(Paid Tier required for gemini-omni-1.2-flash video) and re-run with --validate-key-only first, "
                    "then --execute-live --authorize-spend-usd <CAP> --confirm-billable."
                )
            print(json.dumps(redact_secrets(report), indent=2))
            return 0

        if not has_env_key:
            report["live_verification_status"] = "BLOCKED_MISSING_CREDENTIALS"
            report["remaining_blocker"] = "GEMINI_API_KEY is unset. Export GEMINI_API_KEY before running live verification."
            print(json.dumps(redact_secrets(report), indent=2))
            return 2

        # Step A: Non-billable metadata check
        img_adapter = rt.providers.get_image_adapter("google_gemini_image")
        vid_adapter = rt.providers.get_video_adapter("google_gemini_video")
        img_ok, img_msg = img_adapter.validate_credential(api_key)
        vid_ok, vid_msg = vid_adapter.validate_credential(api_key)
        report["credential_validation"] = {
            "image_model_accessible": img_ok,
            "image_message": img_msg,
            "video_model_accessible": vid_ok,
            "video_message": vid_msg,
        }

        if args.validate_key_only:
            report["live_verification_status"] = "KEY_VALIDATED_NON_BILLABLE_ONLY"
            print(json.dumps(redact_secrets(report), indent=2))
            return 0 if (img_ok and vid_ok) else 3

        # Step B: Fail-closed authorization checks before any paid execution
        if args.authorize_spend_usd <= 0.0 or not args.confirm_billable:
            report["live_verification_status"] = "BLOCKED_AUTHORIZATION_REQUIRED"
            report["error"] = (
                "Refusing paid request: must supply BOTH --authorize-spend-usd <amount > 0> AND --confirm-billable "
                "after reviewing pre_flight_cost_disclosure."
            )
            print(json.dumps(redact_secrets(report), indent=2))
            return 4

        user = rt.repo.update_user_settings(user.id, daily_spend_cap_usd=float(args.authorize_spend_usd))
        report["authorized_spend_cap_usd"] = user.daily_spend_cap_usd

        # Execute 1 live Image generation
        img_quote = rt.jobs.request_quote(user=user, plan=img_plan, provider_id="google_gemini_image", model_id=IMAGE_MODEL)
        try:
            img_job, img_asset, img_review = rt.jobs.submit_approved_job(
                user=user,
                plan=img_plan,
                quote_id=img_quote.quote_id,
                confirmation_token=img_quote.confirmation_token,
                explicit_user_confirmed=True,
                idempotency_key=f"live_smoke_img_{int(time.time())}",
            )
            report["image_result"] = {
                "job_id": img_job.id,
                "status": img_job.status.value,
                "provider_job_id": img_job.provider_job_id,
                "error_category": img_job.error_category.value if img_job.error_category else None,
                "error_message": img_job.error_message,
                "asset": {
                    "id": img_asset.id,
                    "filename": img_asset.filename,
                    "size_bytes": img_asset.size_bytes,
                    "dimensions": f"{img_asset.width}x{img_asset.height}",
                    "sha256": img_asset.sha256,
                }
                if img_asset
                else None,
                "advisory_qc": {
                    "verdict": img_review.advisory_verdict.value,
                    "weighted_score": img_review.weighted_score,
                    "inspection_coverage": img_review.inspection_coverage,
                }
                if img_review
                else None,
            }
        except ProviderAdapterError as exc:
            report["image_result"] = {"blocked_category": exc.category.value, "message": redact_secrets(str(exc))}

        # Execute 1 live Video generation (unless --skip-video)
        if not args.skip_video:
            fresh_user = rt.repo.get_user_profile(user.id) or user
            vid_quote = rt.jobs.request_quote(user=fresh_user, plan=vid_plan, provider_id="google_gemini_video", model_id=VIDEO_MODEL)
            try:
                vid_job, vid_asset, vid_review = rt.jobs.submit_approved_job(
                    user=fresh_user,
                    plan=vid_plan,
                    quote_id=vid_quote.quote_id,
                    confirmation_token=vid_quote.confirmation_token,
                    explicit_user_confirmed=True,
                    idempotency_key=f"live_smoke_vid_{int(time.time())}",
                )
                deadline = time.time() + max(10, args.poll_timeout_s)
                polls = 0
                while vid_job.status in {JobStatus.QUEUED, JobStatus.PROCESSING} and time.time() < deadline:
                    time.sleep(5)
                    polls += 1
                    vid_job, vid_asset, vid_review = rt.jobs.poll_job(fresh_user.id, vid_job.id)
                    if vid_job.status == JobStatus.UNKNOWN:
                        break  # NEVER blindly retry uncertain state!

                report["video_result"] = {
                    "job_id": vid_job.id,
                    "status": vid_job.status.value,
                    "provider_job_id": vid_job.provider_job_id,
                    "poll_count": polls,
                    "error_category": vid_job.error_category.value if vid_job.error_category else None,
                    "error_message": vid_job.error_message,
                    "asset": {
                        "id": vid_asset.id,
                        "filename": vid_asset.filename,
                        "size_bytes": vid_asset.size_bytes,
                        "dimensions": f"{vid_asset.width}x{vid_asset.height}",
                        "duration_s": vid_asset.duration_s,
                        "fps": vid_asset.fps,
                        "sha256": vid_asset.sha256,
                    }
                    if vid_asset
                    else None,
                    "advisory_qc": {
                        "verdict": vid_review.advisory_verdict.value,
                        "weighted_score": vid_review.weighted_score,
                        "inspection_coverage": vid_review.inspection_coverage,
                    }
                    if vid_review
                    else None,
                }
            except ProviderAdapterError as exc:
                report["video_result"] = {"blocked_category": exc.category.value, "message": redact_secrets(str(exc))}

        final_user = rt.repo.get_user_profile(user.id) or user
        report["spend_incurred_usd"] = final_user.spent_today_usd
        report["live_verification_status"] = "COMPLETED"
        print(json.dumps(redact_secrets(report), indent=2))
        return 0
    finally:
        if tmp_ctx is not None:
            tmp_ctx.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
