"""FOXAI Task Management Platform — FastAPI Backend."""
import logging
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from backend.config import settings
from backend.database import init_db, SessionLocal
from backend.services.auth_service import seed_admin
from backend.routers import auth, tasks, users, reports
from backend.platforms import zalo_adapter, facebook_adapter, whatsapp_adapter

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing database...")
    init_db()
    db = SessionLocal()
    try:
        seed_admin(db)
        logger.info(f"Admin account ready: {settings.admin_email}")
    finally:
        db.close()

    # Start Telegram bot in background thread
    if settings.telegram_bot_token:
        from backend.platforms.telegram_adapter import run_telegram_bot
        t = threading.Thread(target=run_telegram_bot, daemon=True)
        t.start()
        logger.info("Telegram bot thread started")

    yield
    # Shutdown — cleanup if needed
    logger.info("Shutting down...")


app = FastAPI(
    title="FOXAI Task Management Platform",
    description="Multi-user, multi-platform task management for FOXAI Delivery Center",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(users.router)
app.include_router(reports.router)

# Platform webhook routers
app.include_router(zalo_adapter.router)
app.include_router(facebook_adapter.router)
app.include_router(whatsapp_adapter.router)

# Serve frontend static files
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/app", StaticFiles(directory=frontend_dir, html=True), name="frontend")

embed_dir = os.path.join(os.path.dirname(__file__), "..", "embed")
if os.path.isdir(embed_dir):
    app.mount("/embed", StaticFiles(directory=embed_dir), name="embed")


@app.get("/")
def root():
    # Redirect to web dashboard if available
    index = os.path.join(frontend_dir, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    return {
        "name": "FOXAI Task Management Platform",
        "version": "2.0.0",
        "docs": "/docs",
        "dashboard": "/app",
    }


@app.get("/health")
def health():
    return {"status": "ok"}
