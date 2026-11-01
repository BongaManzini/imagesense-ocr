# ==============================================================================
# ImageSense-OCR: Production Multi-Stage Containerfile
# Packages Tesseract OCR engine, OpenCV headless dependencies, and Gunicorn WSGI.
# ==============================================================================

# Stage 1: Build virtual environment and Python wheels
FROM python:3.12-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /install

# Install compile-time dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# ==============================================================================
# Stage 2: Minimal Production Runtime
# ==============================================================================
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    FLASK_ENV=production \
    PORT=5000

# Install runtime system libraries:
# - tesseract-ocr & language packs
# - libgl1 & libglib2.0-0 (provides OpenGL and glib for OpenCV / cv2)
# - poppler-utils (for pdf2image rendering)
# - curl (for container healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtualenv from builder stage
COPY --from=builder /opt/venv /opt/venv

# Create unprivileged system user and group for security
RUN groupadd -r -g 1001 imagesense && \
    useradd -r -u 1001 -g imagesense -d /app -s /sbin/nologin -c "ImageSense Service Account" imagesense

WORKDIR /app

# Ensure storage directories exist and assign permissions
RUN mkdir -p /app/uploads /app/processed /app/static /app/templates && \
    chown -R imagesense:imagesense /app

# Copy application source code with correct ownership
COPY --chown=imagesense:imagesense . /app/

# Switch to non-root user
USER imagesense

EXPOSE 5000

# Container healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# Production WSGI server with Gunicorn: 3 workers, 2 threads per worker, 120s timeout
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "--threads", "2", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
