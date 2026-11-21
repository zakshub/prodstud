"""Private content-addressed media storage with magic-byte validation, dimension/duration probing, and safe export."""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from prodstud.security import sanitize_download_filename

MAX_REFERENCE_PIXELS = 25_000_000  # 25 MP ceiling prevents Pillow decompression bomb memory exhaustion
Image.MAX_IMAGE_PIXELS = MAX_REFERENCE_PIXELS

ALLOWED_REFERENCE_MIMES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}

ALLOWED_GENERATED_MIMES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
}


class MediaValidationError(ValueError):
    """Raised when uploaded or generated media fails format, signature, or size verification."""


@dataclass(frozen=True)
class StoredMedia:
    relpath: str
    full_path: Path
    mime_type: str
    size_bytes: int
    sha256: str
    width: int | None
    height: int | None
    duration_s: float | None = None
    fps: float | None = None


def probe_video_metadata(video_path: Path) -> dict[str, Any]:
    """Use ffprobe when available to inspect real MP4 streams deterministically."""
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return {}
        data = json.loads(proc.stdout)
        vstream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
        fmt = data.get("format", {})
        width = int(vstream["width"]) if vstream and vstream.get("width") else None
        height = int(vstream["height"]) if vstream and vstream.get("height") else None
        duration = None
        if vstream and vstream.get("duration"):
            duration = float(vstream["duration"])
        elif fmt.get("duration"):
            duration = float(fmt["duration"])
        fps = None
        raw_rate = (vstream or {}).get("avg_frame_rate") or (vstream or {}).get("r_frame_rate")
        if raw_rate and "/" in raw_rate:
            num, den = raw_rate.split("/", 1)
            if float(den) > 0:
                fps = round(float(num) / float(den), 3)
        return {
            "width": width,
            "height": height,
            "duration_s": round(duration, 3) if duration is not None else None,
            "fps": fps,
            "codec": (vstream or {}).get("codec_name"),
            "nb_frames": int(vstream["nb_frames"]) if vstream and str(vstream.get("nb_frames", "")).isdigit() else None,
        }
    except Exception:
        return {}


class AssetStore:
    """Private filesystem store organizing references and generated outputs by SHA-256 content hash."""

    def __init__(self, base_dir: Path, max_reference_bytes: int = 15 * 1024 * 1024):
        self.base_dir = base_dir.resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.max_reference_bytes = max_reference_bytes

    def store_reference_image(self, data: bytes, declared_mime: str | None = None) -> StoredMedia:
        if not data:
            raise MediaValidationError("Uploaded reference file is empty.")
        if len(data) > self.max_reference_bytes:
            raise MediaValidationError(f"Reference image exceeds max size of {self.max_reference_bytes // (1024 * 1024)} MB.")

        try:
            with Image.open(io.BytesIO(data)) as img:
                img.verify()
            with Image.open(io.BytesIO(data)) as img:
                fmt = (img.format or "").upper()
                width, height = img.size
        except Image.DecompressionBombError as exc:
            raise MediaValidationError("Uploaded image exceeds safe pixel ceiling (25 MP maximum).") from exc
        except Exception as exc:
            raise MediaValidationError("Uploaded file is not a valid PNG, JPEG, or WebP image.") from exc

        if width * height > MAX_REFERENCE_PIXELS:
            raise MediaValidationError("Uploaded image exceeds safe pixel ceiling (25 MP maximum).")

        fmt_to_mime = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
        actual_mime = fmt_to_mime.get(fmt)
        if not actual_mime or actual_mime not in ALLOWED_REFERENCE_MIMES:
            raise MediaValidationError(f"Unsupported image format '{fmt}'. Only PNG, JPEG, and WebP are permitted.")
        if declared_mime and declared_mime.lower() not in {actual_mime, "image/jpg"}:
            # Allow image/jpg alias for JPEG; reject mismatched polyglots
            if not (declared_mime.lower() == "image/jpg" and actual_mime == "image/jpeg"):
                raise MediaValidationError(f"Declared MIME '{declared_mime}' does not match detected image format '{actual_mime}'.")

        return self._write_blob("references", data, actual_mime, width=width, height=height)

    def store_generated_media(self, data: bytes, mime_type: str) -> StoredMedia:
        mime = mime_type.lower().strip()
        if mime == "image/jpg":
            mime = "image/jpeg"
        if mime not in ALLOWED_GENERATED_MIMES:
            raise MediaValidationError(f"Unsupported generated MIME type: {mime_type}")
        if not data:
            raise MediaValidationError("Generated media payload is empty.")

        width = height = None
        duration_s = fps = None
        if mime.startswith("image/"):
            with Image.open(io.BytesIO(data)) as img:
                width, height = img.size
            return self._write_blob("generated", data, mime, width=width, height=height)

        stored = self._write_blob("generated", data, mime)
        probe = probe_video_metadata(stored.full_path)
        return StoredMedia(
            relpath=stored.relpath,
            full_path=stored.full_path,
            mime_type=stored.mime_type,
            size_bytes=stored.size_bytes,
            sha256=stored.sha256,
            width=probe.get("width"),
            height=probe.get("height"),
            duration_s=probe.get("duration_s"),
            fps=probe.get("fps"),
        )

    def _write_blob(
        self,
        bucket: str,
        data: bytes,
        mime_type: str,
        *,
        width: int | None = None,
        height: int | None = None,
    ) -> StoredMedia:
        ext = ALLOWED_GENERATED_MIMES[mime_type]
        digest = hashlib.sha256(data).hexdigest()
        subdir = self.base_dir / bucket / digest[:2]
        subdir.mkdir(parents=True, exist_ok=True)
        filename = f"{digest}{ext}"
        full_path = subdir / filename
        if not full_path.exists():
            tmp = subdir / f"{filename}.tmp"
            tmp.write_bytes(data)
            tmp.replace(full_path)
        relpath = f"{bucket}/{digest[:2]}/{filename}"
        return StoredMedia(
            relpath=relpath,
            full_path=full_path,
            mime_type=mime_type,
            size_bytes=len(data),
            sha256=digest,
            width=width,
            height=height,
        )

    def resolve(self, relpath: str) -> Path:
        candidate = (self.base_dir / relpath).resolve()
        if not candidate.is_relative_to(self.base_dir):
            raise MediaValidationError("Path traversal blocked.")
        if not candidate.exists():
            raise FileNotFoundError(f"Asset file not found: {relpath}")
        return candidate

    def read_bytes(self, relpath: str) -> bytes:
        return self.resolve(relpath).read_bytes()

    def build_export_zip(self, items: list[tuple[str, str, dict[str, Any]]]) -> bytes:
        """Package media files + sanitized provenance JSON sidecars into an in-memory ZIP archive (Zip-Slip safe)."""
        buf = io.BytesIO()
        used_names: set[str] = set()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for idx, (relpath, export_filename, sidecar) in enumerate(items, start=1):
                safe_name = sanitize_download_filename(export_filename, fallback=f"asset_{idx}.bin")
                if safe_name in used_names:
                    stem, dot, ext = safe_name.rpartition(".")
                    safe_name = f"{stem}_{idx}.{ext}" if dot else f"{safe_name}_{idx}"
                used_names.add(safe_name)
                media_bytes = self.read_bytes(relpath)
                zf.writestr(safe_name, media_bytes)
                sidecar_name = f"{Path(safe_name).stem}.provenance.json"
                zf.writestr(
                    sidecar_name,
                    json.dumps(sidecar, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                )
        return buf.getvalue()

    def total_usage_bytes(self) -> int:
        total = 0
        for p in self.base_dir.rglob("*"):
            if p.is_file():
                total += p.stat().st_size
        return total
