"""Core domain enumerations for Production Studio."""

from __future__ import annotations

from enum import Enum


class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


class TaskMode(str, Enum):
    NEW_GENERATION = "NEW_GENERATION"
    STRICT_PRESERVATION_EDIT = "STRICT_PRESERVATION_EDIT"
    SELECTIVE_EDIT = "SELECTIVE_EDIT"
    PRODUCT_IMAGE = "PRODUCT_IMAGE"
    PORTRAIT = "PORTRAIT"
    FASHION_EDITORIAL = "FASHION_EDITORIAL"
    LIFESTYLE_DOCUMENTARY = "LIFESTYLE_DOCUMENTARY"
    CINEMATIC_STILL = "CINEMATIC_STILL"
    VIDEO_SINGLE_SHOT = "VIDEO_SINGLE_SHOT"
    VIDEO_MULTI_SHOT_SEQUENCE = "VIDEO_MULTI_SHOT_SEQUENCE"
    VIDEO_EXTENSION = "VIDEO_EXTENSION"


class ReferenceRole(str, Enum):
    IDENTITY = "identity"
    STYLE = "style"
    COMPOSITION = "composition"
    ENVIRONMENT = "environment"
    PRODUCT = "product"
    MOTION = "motion"
    START_FRAME = "start_frame"
    END_FRAME = "end_frame"


class JobStatus(str, Enum):
    DRAFT = "draft"
    AWAITING_APPROVAL = "awaiting_approval"
    SUBMITTED = "submitted"
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"  # Required when network timeout makes provider acceptance uncertain


class CapabilitySupport(str, Enum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNVERIFIED = "unverified"
    DEPRECATED = "deprecated"
    PROVIDER_CONDITIONAL = "provider_conditional"


class ProtocolDisposition(str, Enum):
    CORE = "core"
    CONDITIONAL = "conditional"
    ADAPTED = "adapted"
    DEFERRED = "deferred"


class QualityVerdict(str, Enum):
    PASS_ADVISORY = "pass_advisory"
    REVIEW_RECOMMENDED = "review_recommended"
    REWORK_RECOMMENDED = "rework_recommended"


class ErrorCategory(str, Enum):
    VALIDATION = "validation"
    SPEND_GUARD = "spend_guard"
    APPROVAL_REQUIRED = "approval_required"
    PROVIDER_AUTH = "provider_auth"
    PROVIDER_REJECTED = "provider_rejected"
    MODERATION = "moderation"
    QUOTA = "quota"
    TIMEOUT_UNKNOWN = "timeout_unknown"
    NETWORK = "network"
    INTERNAL = "internal"
