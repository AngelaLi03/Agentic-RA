"""FastAPI app: lifespan-managed shared clients + route registration."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from agentic_ra.api.deps import build_context
from agentic_ra.api.routes import router
from agentic_ra.config import get_settings
from agentic_ra.logging import configure_logging, get_logger

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    ctx = build_context(settings)
    app.state.ctx = ctx
    log.info("startup", model=settings.agent_model, tools=len(ctx.registry))
    try:
        yield
    finally:
        await ctx.http.aclose()
        await ctx.anthropic.close()
        log.info("shutdown")


def create_app() -> FastAPI:
    app = FastAPI(title="Agentic-RA", version="0.1.0", lifespan=lifespan)
    app.include_router(router)

    @app.exception_handler(ValueError)
    async def _value_error(_: Any, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    return app


app = create_app()
