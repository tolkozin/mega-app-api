"""FastAPI backend for Revenue Map financial modeling API."""

import os
import time
import logging

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from collections import defaultdict

from routers import models, export

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("revenuemap")

app = FastAPI(title="Revenue Map API", version="1.0.0")

# --------------- CORS ---------------

_allowed_origins = os.environ.get(
    "CORS_ORIGINS",
    "https://revenuemap.app,https://www.revenuemap.app,http://localhost:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# --------------- Rate limiting middleware ---------------

_rate_store: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_REQUESTS = int(os.environ.get("RATE_LIMIT_REQUESTS", "30"))
RATE_LIMIT_WINDOW = int(os.environ.get("RATE_LIMIT_WINDOW", "60"))


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)

    client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown").split(",")[0].strip()
    now = time.time()

    # Clean old entries
    _rate_store[client_ip] = [t for t in _rate_store[client_ip] if now - t < RATE_LIMIT_WINDOW]

    if len(_rate_store[client_ip]) >= RATE_LIMIT_REQUESTS:
        logger.warning("Rate limit exceeded for %s", client_ip)
        return Response(
            content='{"error":"Too many requests"}',
            status_code=429,
            media_type="application/json",
            headers={"Retry-After": str(RATE_LIMIT_WINDOW)},
        )

    _rate_store[client_ip].append(now)
    return await call_next(request)


# --------------- Request logging middleware ---------------

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000
    logger.info(
        "%s %s → %d (%.0fms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


# --------------- Routers ---------------

app.include_router(models.router)
app.include_router(export.router)


@app.get("/")
def root():
    return {"status": "ok", "service": "revenuemap-api"}
