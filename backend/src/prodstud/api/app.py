"""FastAPI application factory with security headers, CORS, routes, and optional static web serving."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from prodstud import __version__
from prodstud.api.routes_auth import router as auth_router
from prodstud.api.routes_production import router as production_router
from prodstud.api.routes_projects import router as projects_router
from prodstud.config import Settings
from prodstud.runtime import AppRuntime


def create_app(settings: Settings | None = None, frontend_dist: Path | None = None) -> FastAPI:
    rt = AppRuntime.create(settings)

    app = FastAPI(
        title="Production Studio API",
        version=__version__,
        docs_url="/api/docs" if not rt.settings.is_production else None,
        redoc_url=None,
    )
    app.state.runtime = rt

    dev_allowed_origins = {
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    }

    if not rt.settings.is_production:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=sorted(dev_allowed_origins),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next: Callable) -> Response:
        # Defense-in-depth CSRF check: block cross-origin browser state-changing requests authenticated by session cookie
        if request.method in {"POST", "PATCH", "PUT", "DELETE"} and request.cookies.get("prodstud_session"):
            origin = (request.headers.get("origin") or "").rstrip("/")
            if origin:
                expected_origin = f"{request.url.scheme}://{request.headers.get('host', request.url.netloc)}".rstrip("/")
                allowed = {expected_origin} if rt.settings.is_production else ({expected_origin} | dev_allowed_origins)
                if origin not in allowed:
                    return Response(
                        content='{"detail":"Cross-origin state-changing request rejected by CSRF guard."}',
                        status_code=403,
                        media_type="application/json",
                    )

        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        if not request.url.path.startswith("/api/docs"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; "
                "style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; "
                "frame-ancestors 'none'; base-uri 'self';"
            )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/health")
    def health() -> dict:
        integrity = rt.db.verify_integrity()
        return {
            "status": "ok",
            "version": __version__,
            "environment": rt.settings.env,
            "database_integrity": integrity,
            "protocols_loaded": len(rt.protocols.entries),
            "local_test_fixture_enabled": rt.settings.enable_local_fixture,
        }

    app.include_router(auth_router)
    app.include_router(projects_router)
    app.include_router(production_router)

    # Optionally serve compiled React frontend (Level 2+ Web Application)
    dist_path = (frontend_dist or (Path(__file__).resolve().parents[4] / "frontend" / "dist")).resolve()
    if dist_path.exists() and (dist_path / "index.html").exists():
        assets_dir = dist_path / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")

        @app.get("/{full_path:path}")
        def serve_spa(full_path: str) -> Response:
            if full_path.startswith("api/"):
                return Response(status_code=404)
            candidate = (dist_path / full_path).resolve()
            if full_path and candidate.exists() and candidate.is_file() and candidate.is_relative_to(dist_path):
                return FileResponse(candidate)
            return FileResponse(dist_path / "index.html")

    return app


app = create_app()
