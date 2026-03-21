"""FastAPI backend for Mega App financial modeling API."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import models, export, stripe_webhook

app = FastAPI(title="Mega App API", version="1.0.0")

# CORS — restrict to known origins in production
_allowed_origins = os.environ.get(
    "CORS_ORIGINS",
    "https://revenuemap.app,https://www.revenuemap.app,http://localhost:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(models.router)
app.include_router(export.router)
app.include_router(stripe_webhook.router)


@app.get("/")
def root():
    return {"status": "ok", "service": "mega-app-api"}
