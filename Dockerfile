# ── Stage 1: Build ──────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime ───────────────────────────────────────────────
FROM python:3.12-slim

LABEL maintainer="Escipion Pedroza"
LABEL description="Google Code Review AI — AI-powered code review API"
LABEL version="1.0.0"

# Security: run as non-root
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY main.py .
COPY config/ config/
COPY src/ src/

# Set ownership
RUN chown -R appuser:appuser /app

USER appuser

# Environment defaults (override with -e or .env)
ENV HOST=0.0.0.0
ENV PORT=8000
ENV LOG_LEVEL=info
ENV DEFAULT_PROVIDER=gemini

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
