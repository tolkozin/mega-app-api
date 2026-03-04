"""FastAPI backend for Mega App financial modeling API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import models, export, stripe_webhook

app = FastAPI(title="Mega App API", version="1.0.0")

# CORS — allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
