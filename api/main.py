"""
ReturnWise HTTP API (FastAPI)
=============================
A thin layer over the existing services and workflow. It contains NO business rules:
validation, agents, decisions and persistence all stay in the Python backend.

Run:  uvicorn api.main:app --reload --port 8000
If frontend/dist exists (after `npm run build`) it is served at "/" as a single-page app.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

import config
from database.db import init_db
from api.routes import router

logger = logging.getLogger("returnwise.api")

FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")


def error_body(code: str, message: str, fields: dict | None = None, **extra) -> dict:
    """The one error shape used by every failing response."""
    body = {"error": {"code": code, "message": message, "fields": fields or {}}}
    body["error"].update(extra)
    return body


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()                      # create / migrate / seed the SQLite file (idempotent)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="ReturnWise API", version=config.APP_VERSION, lifespan=lifespan,
                  description="Recommendation-only return resolution. No refunds are executed.")

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        fields = {}
        for err in exc.errors():
            loc = [str(p) for p in err["loc"] if p not in ("body", "query", "path")]
            fields[".".join(loc) or "request"] = err["msg"]
        return JSONResponse(status_code=422, content=error_body(
            "validation_error", "The request is not valid.", fields))

    @app.exception_handler(StarletteHTTPException)   # also catches router-level 404/405
    async def _http(request: Request, exc: StarletteHTTPException):
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return JSONResponse(status_code=exc.status_code, content=error_body(code, str(exc.detail)))

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception):
        logger.error("Unhandled %s on %s", type(exc).__name__, request.url.path)   # no stack to client
        return JSONResponse(status_code=500, content=error_body(
            "internal_error", "Something went wrong on the server. Nothing was changed by this call."))

    app.include_router(router, prefix="/api")

    if os.path.isdir(FRONTEND_DIST):
        assets = os.path.join(FRONTEND_DIST, "assets")
        if os.path.isdir(assets):
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Unknown API route.")
            candidate = os.path.realpath(os.path.join(FRONTEND_DIST, path))
            if path and candidate.startswith(os.path.realpath(FRONTEND_DIST)) and os.path.isfile(candidate):
                return FileResponse(candidate)
            return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))   # client-side routing

    return app


app = create_app()
