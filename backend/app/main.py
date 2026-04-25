"""FastAPI entrypoint: Market Snapshot API."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.jobs.snapshot_job import ist_now, run_snapshot_pipeline
from app.routers.sentiment import router as sentiment_router
from app.routers.snapshot import router as snapshot_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler: BackgroundScheduler | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler
    settings = get_settings()
    scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(
        lambda: run_snapshot_pipeline(persist=True),
        CronTrigger(hour=settings.snapshot_cron_hour, minute=settings.snapshot_cron_minute),
        id="daily_snapshot",
        replace_existing=True,
    )
    if settings.intraday_refresh_minutes and settings.intraday_refresh_minutes > 0:
        scheduler.add_job(
            lambda: run_snapshot_pipeline(persist=True),
            "interval",
            minutes=settings.intraday_refresh_minutes,
            id="intraday_snapshot",
            replace_existing=True,
        )
    scheduler.start()
    logger.info(
        "Scheduler started: daily at %02d:%02d IST; intraday=%s min",
        settings.snapshot_cron_hour,
        settings.snapshot_cron_minute,
        settings.intraday_refresh_minutes or "off",
    )
    yield
    if scheduler:
        scheduler.shutdown(wait=False)
        scheduler = None


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Market Snapshot API", version="1.0.0", lifespan=lifespan)
    origins = [o.strip() for o in settings.api_cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(snapshot_router)
    app.include_router(sentiment_router)

    @app.get("/")
    def root():
        """No HTML landing page — API only. Use /docs for Swagger or the links below."""
        return {
            "service": "Market Snapshot API",
            "docs": "/docs",
            "openapi": "/openapi.json",
            "health": "/health",
            "snapshot_today": "/snapshot/today",
            "snapshot_history": "/snapshot/history?days=30",
            "sentiment_x": "/sentiment/x",
            "refresh": "POST /snapshot/refresh",
            "dashboard": "With Docker Compose UI: http://localhost:8080/",
        }

    @app.get("/health")
    def health():
        return {"status": "ok", "ist": ist_now().isoformat()}

    return app


app = create_app()
