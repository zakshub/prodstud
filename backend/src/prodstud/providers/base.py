"""Typed abstract interfaces for independent Image and Video provider adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import os
import ssl
from typing import Any

import httpx

from prodstud.domain.enums import ErrorCategory, JobStatus
from prodstud.domain.models import ProductionPlanRecord, ProviderModelCapability


def build_http_client(timeout_seconds: float) -> httpx.Client:
    """Create an httpx.Client resilient to NO_PROXY IPv6 bracket entries while honoring HTTP(S)_PROXY and CA certs."""
    try:
        return httpx.Client(timeout=timeout_seconds)
    except httpx.InvalidURL:
        proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy") or os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
        cafile = os.getenv("SSL_CERT_FILE") or os.getenv("REQUESTS_CA_BUNDLE")
        verify: ssl.SSLContext | bool = ssl.create_default_context(cafile=cafile) if cafile else True
        return httpx.Client(timeout=timeout_seconds, proxy=proxy, verify=verify, trust_env=False)


class ProviderAdapterError(RuntimeError):
    """Structured error carrying classification and ambiguous-acceptance flag for billing safety."""

    def __init__(
        self,
        message: str,
        *,
        category: ErrorCategory,
        provider_may_have_accepted: bool = False,
        provider_job_id: str | None = None,
    ):
        super().__init__(message)
        self.category = category
        self.provider_may_have_accepted = provider_may_have_accepted
        self.provider_job_id = provider_job_id


@dataclass
class ProviderSubmissionResult:
    status: JobStatus  # succeeded (sync) | submitted / queued / processing (async)
    provider_job_id: str | None = None
    media_bytes: bytes | None = None
    mime_type: str | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)
    reported_cost_usd: float = 0.0


@dataclass
class ReferencePayload:
    reference_id: str
    filename: str
    role: str
    mime_type: str
    data: bytes


class ImageProviderAdapter(ABC):
    """Dedicated interface for image generation adapters."""

    provider_id: str
    provider_name: str

    @abstractmethod
    def capabilities(self) -> list[ProviderModelCapability]:
        ...

    @abstractmethod
    def validate_request(
        self,
        plan: ProductionPlanRecord,
        model_id: str,
        references: list[ReferencePayload],
    ) -> list[str]:
        """Return list of validation errors (empty if valid)."""
        ...

    @abstractmethod
    def submit(
        self,
        *,
        plan: ProductionPlanRecord,
        model_id: str,
        references: list[ReferencePayload],
        api_key: str | None,
        idempotency_key: str,
        previous_provider_job_id: str | None = None,
        variation_index: int = 1,
        variation_total: int = 1,
    ) -> ProviderSubmissionResult:
        ...

    def poll_status(self, *, provider_job_id: str, model_id: str, api_key: str | None) -> ProviderSubmissionResult:
        raise NotImplementedError("Synchronous image adapter does not require polling.")

    def cancel(self, *, provider_job_id: str, api_key: str | None) -> bool:
        return False

    def validate_credential(self, api_key: str) -> tuple[bool, str]:
        return True, "No credential required."


class VideoProviderAdapter(ABC):
    """Dedicated interface for asynchronous video generation adapters."""

    provider_id: str
    provider_name: str

    @abstractmethod
    def capabilities(self) -> list[ProviderModelCapability]:
        ...

    @abstractmethod
    def validate_request(
        self,
        plan: ProductionPlanRecord,
        model_id: str,
        references: list[ReferencePayload],
    ) -> list[str]:
        ...

    @abstractmethod
    def submit(
        self,
        *,
        plan: ProductionPlanRecord,
        model_id: str,
        references: list[ReferencePayload],
        api_key: str | None,
        idempotency_key: str,
        previous_provider_job_id: str | None = None,
    ) -> ProviderSubmissionResult:
        ...

    @abstractmethod
    def poll_status(self, *, provider_job_id: str, model_id: str, api_key: str | None) -> ProviderSubmissionResult:
        ...

    @abstractmethod
    def cancel(self, *, provider_job_id: str, api_key: str | None) -> bool:
        ...

    def validate_credential(self, api_key: str) -> tuple[bool, str]:
        return True, "No credential required."
