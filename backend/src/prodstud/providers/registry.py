"""Provider Registry uniting separate Image and Video provider adapters and capability discovery."""

from __future__ import annotations

from prodstud.domain.enums import CapabilitySupport, MediaType
from prodstud.domain.models import ProviderModelCapability
from prodstud.providers.base import ImageProviderAdapter, VideoProviderAdapter
from prodstud.providers.google_image import GoogleImageAdapter
from prodstud.providers.google_video import GoogleVideoAdapter
from prodstud.providers.local_test import LocalTestImageAdapter, LocalTestVideoAdapter


class ProviderRegistry:
    """Discovers verified image and video adapters independently."""

    def __init__(self, *, enable_local_fixture: bool):
        self.image_adapters: dict[str, ImageProviderAdapter] = {}
        self.video_adapters: dict[str, VideoProviderAdapter] = {}

        google_img = GoogleImageAdapter()
        google_vid = GoogleVideoAdapter()
        self.image_adapters[google_img.provider_id] = google_img
        self.video_adapters[google_vid.provider_id] = google_vid

        if enable_local_fixture:
            local_img = LocalTestImageAdapter()
            local_vid = LocalTestVideoAdapter()
            self.image_adapters[local_img.provider_id] = local_img
            self.video_adapters[local_vid.provider_id] = local_vid

    def list_capabilities(self, media_type: MediaType | None = None) -> list[ProviderModelCapability]:
        caps: list[ProviderModelCapability] = []
        if media_type in (None, MediaType.IMAGE):
            for adapter in self.image_adapters.values():
                caps.extend(adapter.capabilities())
        if media_type in (None, MediaType.VIDEO):
            for adapter in self.video_adapters.values():
                caps.extend(adapter.capabilities())
        return caps

    def get_capability(self, media_type: MediaType, provider_id: str, model_id: str) -> ProviderModelCapability | None:
        for cap in self.list_capabilities(media_type):
            if cap.provider_id == provider_id and cap.model_id == model_id:
                return cap
        return None

    def resolve_capability(
        self,
        media_type: MediaType,
        provider_id: str | None = None,
        model_id: str | None = None,
        *,
        prefer_google: bool = True,
    ) -> ProviderModelCapability:
        caps = self.list_capabilities(media_type)
        if provider_id and model_id:
            match = self.get_capability(media_type, provider_id, model_id)
            if not match:
                raise ValueError(f"Unsupported provider/model combination: {provider_id}/{model_id}")
            return match
        if provider_id:
            by_provider = [c for c in caps if c.provider_id == provider_id and c.support_status == CapabilitySupport.SUPPORTED]
            if not by_provider:
                raise ValueError(f"No supported {media_type.value} model for provider '{provider_id}'.")
            return by_provider[0]
        if model_id:
            by_model = [c for c in caps if c.model_id == model_id]
            if not by_model:
                raise ValueError(f"Unknown {media_type.value} model '{model_id}'.")
            return by_model[0]

        if prefer_google:
            preferred = "gemini-nano-banana-2.1" if media_type == MediaType.IMAGE else "gemini-omni-1.2-flash"
            found = next((c for c in caps if c.model_id == preferred), None)
            if found:
                return found

        supported = [c for c in caps if c.support_status == CapabilitySupport.SUPPORTED]
        if not supported:
            raise ValueError(f"No supported {media_type.value} providers available.")
        return supported[0]

    def get_image_adapter(self, provider_id: str) -> ImageProviderAdapter:
        if provider_id not in self.image_adapters:
            raise ValueError(f"Unknown image provider: {provider_id}")
        return self.image_adapters[provider_id]

    def get_video_adapter(self, provider_id: str) -> VideoProviderAdapter:
        if provider_id not in self.video_adapters:
            raise ValueError(f"Unknown video provider: {provider_id}")
        return self.video_adapters[provider_id]

    def credential_provider_key(self, provider_id: str) -> str:
        """Both Google image and Google video Gemini API adapters share the 'google' server-side API key slot."""
        if provider_id.startswith("google_"):
            return "google"
        return provider_id
