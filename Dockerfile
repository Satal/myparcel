# MyParcel Dockerfile
#
# Two build targets:
#   - default: Lightweight, no browser automation (Royal Mail, DPD work)
#   - full: Includes Playwright for JS-heavy sites (Evri, etc.)
#
# Build lightweight version:
#   docker build -t myparcel .
#
# Build full version with browser support:
#   docker build --target full -t myparcel:full .

# ==============================================================================
# Stage 1: Base image with Python dependencies
# ==============================================================================
FROM python:3.12-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (without browser extras)
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application code
COPY src/ src/
COPY static/ static/

# Create data directory
RUN mkdir -p data

# Expose port
EXPOSE 8000

# ==============================================================================
# Stage 2: Lightweight image (default) - no browser automation
# ==============================================================================
FROM base AS default

# Run the application
CMD ["uvicorn", "myparcel.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ==============================================================================
# Stage 3: Full image with Playwright for JS-heavy carriers (Evri, etc.)
# ==============================================================================
FROM base AS full

# Install Playwright and browser dependencies
RUN pip install --no-cache-dir playwright \
    && playwright install chromium --with-deps

# Note: For Chromium to work properly, run with:
#   docker run --ipc=host myparcel:full
# Or:
#   docker run --cap-add=SYS_ADMIN myparcel:full

CMD ["uvicorn", "myparcel.main:app", "--host", "0.0.0.0", "--port", "8000"]
