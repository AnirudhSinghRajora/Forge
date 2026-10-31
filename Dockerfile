# One container: FastAPI serves the built web app, so there is one URL and no CORS to configure.
FROM docker.io/library/node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM docker.io/library/python:3.12-slim-bookworm
# WeasyPrint needs Pango; fonts-noto-core carries the Devanagari and Telugu faces used in the PDF.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0 libfontconfig1 \
      fonts-noto-core fonts-noto-mono \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv
WORKDIR /srv/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/app ./app
COPY backend/data/policy/clauses.jsonl backend/data/policy/key_rules.json ./data/policy/
COPY --from=web /web/dist /srv/web/dist
# One process, on purpose: rate limits, the run queue and the scheduler live in memory, so no --workers.
# Set PUBLIC_WEB_URL, and TRUST_PROXY=true behind a proxy that sets X-Forwarded-*.
# Mount a persistent volume at /data: the sealed evidence behind every QR verify link lives there.
ENV PORT=8080 PYTHONUNBUFFERED=1 VAR_DIR=/data FASALSAAKSHI_VAR_DIR=/data
RUN mkdir -p /data
EXPOSE 8080
CMD ["sh", "-c", "exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
