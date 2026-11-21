"""Google Gemini Multimodal Vision QC Provider Adapter (Isolated inside providers/ boundary).

Targets verified Gemini Developer API generateContent endpoint (gemini-3.5-flash-lite / gemini-2.5-flash)
with x-goog-api-key header, secret redaction, and explicit timeout->UNKNOWN billing safety.
"""

from __future__ import annotations

import base64
from typing import Any, Callable

import httpx

from prodstud.domain.enums import ErrorCategory
from prodstud.engine.vision_qc import VisionImageInput, VisionQCResponse
from prodstud.providers.base import ProviderAdapterError, build_http_client
from prodstud.security import redact_secrets

DEFAULT_GOOGLE_VISION_MODEL = "gemini-3.5-flash-lite"


class GoogleVisionQCAdapter:
    """Provider adapter executing multimodal Vision QC prompts against Google Gemini REST API."""

    provider_id = "google_gemini_image"

    def __init__(
        self,
        *,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        model_id: str = DEFAULT_GOOGLE_VISION_MODEL,
        timeout_seconds: float = 60.0,
        http_client_factory: Callable[[float], httpx.Client] = build_http_client,
    ):
        self.base_url = base_url.rstrip("/")
        self.model_id = model_id
        self.timeout_seconds = timeout_seconds
        self.http_client_factory = http_client_factory

    def inspect_images(
        self,
        *,
        prompt: str,
        images: list[VisionImageInput],
        api_key: str,
    ) -> VisionQCResponse:
        if not api_key or len(api_key.strip()) < 10:
            raise ProviderAdapterError(
                "Active Google Gemini API key is required for optional multimodal Vision QC.",
                category=ErrorCategory.PROVIDER_AUTH,
            )

        parts: list[dict[str, Any]] = [{"text": prompt}]
        for item in images:
            parts.append({"text": item.label})
            parts.append(
                {
                    "inlineData": {
                        "mimeType": item.mime_type or "image/png",
                        "data": base64.b64encode(item.data).decode("ascii"),
                    }
                }
            )

        body = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
        }

        try:
            with self.http_client_factory(self.timeout_seconds) as client:
                resp = client.post(
                    f"{self.base_url}/models/{self.model_id}:generateContent",
                    headers={
                        "x-goog-api-key": api_key.strip(),
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
        except httpx.TimeoutException as exc:
            raise ProviderAdapterError(
                "Multimodal Vision QC request timed out. Status is UNKNOWN; do not blindly resubmit.",
                category=ErrorCategory.TIMEOUT_UNKNOWN,
                provider_may_have_accepted=True,
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderAdapterError(
                f"Network error contacting Google Gemini Vision QC: {redact_secrets(str(exc))}",
                category=ErrorCategory.NETWORK,
            ) from exc

        if resp.status_code in {401, 403}:
            raise ProviderAdapterError(
                f"Google API rejected Vision QC request (HTTP {resp.status_code}).",
                category=ErrorCategory.PROVIDER_AUTH,
            )
        if resp.status_code == 429:
            raise ProviderAdapterError(
                "Google API quota/rate limit exceeded during Vision QC (HTTP 429).",
                category=ErrorCategory.QUOTA,
            )
        if resp.status_code >= 400:
            raise ProviderAdapterError(
                f"Google Gemini Vision QC rejected request (HTTP {resp.status_code}): {redact_secrets(resp.text[:400])}",
                category=ErrorCategory.PROVIDER_REJECTED,
            )

        payload = resp.json()
        raw_text = ""
        for cand in payload.get("candidates") or []:
            for part in (cand.get("content") or {}).get("parts") or []:
                if isinstance(part, dict) and part.get("text"):
                    raw_text += str(part["text"])

        usage = payload.get("usageMetadata") or {}
        in_tok = int(usage.get("promptTokenCount") or 0)
        out_tok = int(usage.get("candidatesTokenCount") or 0)
        reported_cost: float | None = None
        if in_tok > 0 or out_tok > 0:
            reported_cost = round((in_tok / 1_000_000) * 0.30 + (out_tok / 1_000_000) * 2.50, 6)

        return VisionQCResponse(
            raw_text=raw_text,
            model_id=self.model_id,
            reported_cost_usd=reported_cost,
            prompt_tokens=in_tok,
            output_tokens=out_tok,
        )
