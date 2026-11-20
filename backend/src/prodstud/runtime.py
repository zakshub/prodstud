"""Shared application runtime wiring used identically by REST API and Level 1 CLI."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from prodstud.config import Settings
from prodstud.engine.orchestrator import ProductionIntelligenceEngine
from prodstud.engine.protocol_registry import ProtocolRegistry
from prodstud.jobs.runner import JobService
from prodstud.providers.policy_gate import PolicyEvaluationGate
from prodstud.providers.registry import ProviderRegistry
from prodstud.security import ApprovalSigner, SecretRedactingFilter, SecretVault
from prodstud.storage.asset_store import AssetStore
from prodstud.storage.database import Database
from prodstud.storage.repositories import Repository


@dataclass
class AppRuntime:
    settings: Settings
    db: Database
    repo: Repository
    store: AssetStore
    vault: SecretVault
    signer: ApprovalSigner
    protocols: ProtocolRegistry
    engine: ProductionIntelligenceEngine
    providers: ProviderRegistry
    policy_gate: PolicyEvaluationGate
    jobs: JobService

    @classmethod
    def create(cls, settings: Settings | None = None) -> "AppRuntime":
        cfg = settings or Settings.from_env()
        cfg.ensure_dirs()

        # Attach global secret redactor to prodstud logger
        logger = logging.getLogger("prodstud")
        if not any(isinstance(f, SecretRedactingFilter) for f in logger.filters):
            logger.addFilter(SecretRedactingFilter())

        db = Database(cfg.db_path)
        repo = Repository(db)
        store = AssetStore(cfg.assets_dir, max_reference_bytes=cfg.max_reference_bytes)
        vault = SecretVault(cfg.data_dir / "master.key", key_override=cfg.master_key_override)
        signer = ApprovalSigner(cfg.data_dir / "approval.key", secret_override=cfg.session_secret_override)
        protocols = ProtocolRegistry(cfg.protocols_path)
        engine = ProductionIntelligenceEngine(protocols)
        providers = ProviderRegistry(enable_local_fixture=cfg.enable_local_fixture)
        policy_gate = PolicyEvaluationGate(signer)
        jobs = JobService(
            repo=repo,
            store=store,
            vault=vault,
            providers=providers,
            policy_gate=policy_gate,
        )
        return cls(
            settings=cfg,
            db=db,
            repo=repo,
            store=store,
            vault=vault,
            signer=signer,
            protocols=protocols,
            engine=engine,
            providers=providers,
            policy_gate=policy_gate,
            jobs=jobs,
        )
