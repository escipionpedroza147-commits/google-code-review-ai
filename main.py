"""Google Code Review AI — FastAPI application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from src.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )
    logger = logging.getLogger("google-code-review-ai")
    logger.info("🚀 Google Code Review AI starting up")
    logger.info(f"   Provider: {settings.default_provider}")
    logger.info(f"   Host: {settings.host}:{settings.port}")
    logger.info(f"   Gemini configured: {bool(settings.gemini_api_key)}")
    logger.info(f"   OpenAI configured: {bool(settings.openai_api_key)}")
    logger.info(f"   GitHub webhook: {bool(settings.github_webhook_secret)}")
    yield
    logger.info("👋 Google Code Review AI shutting down")


app = FastAPI(
    title="Google Code Review AI",
    description="AI-powered code review with the precision of a Google Staff Engineer",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        reload=True,
    )
