"""Environment-isolated configuration for Production Studio (development / test / production)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _repo_root() -> Path:
    # backend/src/prodstud/config.py -> parents[3] is repo root
    return Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    env: str
    data_dir: Path
    db_path: Path
    assets_dir: Path
    snapshots_dir: Path
    protocols_path: Path
    enable_local_fixture: bool
    default_daily_spend_cap_usd: float
    master_key_override: str | None
    session_secret_override: str | None
    host: str
    port: int
    max_reference_bytes: int = 15 * 1024 * 1024  # 15 MB strict upload limit

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @classmethod
    def from_env(cls, data_dir_override: Path | str | None = None, env_override: str | None = None) -> "Settings":
        root = _repo_root()
        env = (env_override or os.getenv("PRODSTUD_ENV", "development")).strip().lower()
        if env not in {"development", "test", "production"}:
            env = "development"

        raw_data_dir = data_dir_override or os.getenv("PRODSTUD_DATA_DIR") or (root / ".prodstud_data")
        data_dir = Path(raw_data_dir).expanduser().resolve()
        db_path = data_dir / "prodstud.sqlite3"
        assets_dir = data_dir / "assets"
        snapshots_dir = data_dir / "snapshots"
        protocols_path = Path(os.getenv("PRODSTUD_PROTOCOLS_PATH", str(root / "data" / "protocols_170.json"))).resolve()

        # Local test fixture is strictly disabled in production unless explicitly overridden in dev/test.
        fixture_env = os.getenv("PRODSTUD_ENABLE_LOCAL_FIXTURE")
        if env == "production":
            enable_fixture = False
        elif fixture_env is None:
            enable_fixture = True
        else:
            enable_fixture = fixture_env.strip().lower() in {"1", "true", "yes", "on"}

        raw_cap = os.getenv("PRODSTUD_DEFAULT_DAILY_SPEND_CAP_USD", "0.00")
        try:
            default_cap = max(0.0, float(raw_cap))
        except ValueError:
            default_cap = 0.0

        return cls(
            env=env,
            data_dir=data_dir,
            db_path=db_path,
            assets_dir=assets_dir,
            snapshots_dir=snapshots_dir,
            protocols_path=protocols_path,
            enable_local_fixture=enable_fixture,
            default_daily_spend_cap_usd=default_cap,
            master_key_override=os.getenv("PRODSTUD_MASTER_KEY") or None,
            session_secret_override=os.getenv("PRODSTUD_SESSION_SECRET") or None,
            host=os.getenv("PRODSTUD_HOST", "127.0.0.1"),
            port=int(os.getenv("PRODSTUD_PORT", "8000")),
        )

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.data_dir, 0o700)
        except OSError:
            pass
