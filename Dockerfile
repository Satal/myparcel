# MyParcel Dockerfile
#
# Two build targets:
#   - default: no browser automation (Relay, DPD, Royal Mail)
#   - full: adds Playwright + Chromium for JS-heavy sites (Evri)
#
#   docker build -t myparcel .
#   docker build --target full -t myparcel:full .
#
# The container starts as root only to hand /app/data to the app user (bind
# mounts are usually root-owned), then drops to that user.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ src/
RUN pip install --no-cache-dir .

COPY static/ static/
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN useradd --system --uid 1000 --user-group --home-dir /app myparcel \
    && mkdir -p data && chown myparcel:myparcel data

EXPOSE 8000
VOLUME ["/app/data"]

HEALTHCHECK --interval=60s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status != 200)"

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "myparcel.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

FROM base AS full

RUN pip install --no-cache-dir playwright \
    && playwright install chromium --with-deps \
    && rm -rf /var/lib/apt/lists/*

# Last stage is what a plain `docker build` produces
FROM base AS default
