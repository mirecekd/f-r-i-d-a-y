# syntax=docker/dockerfile:1
FROM node:24-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
# vite.config.ts builds into ../backend/static
RUN mkdir -p /backend && npm run build

FROM python:3.12-slim
WORKDIR /srv
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY backend/mcp_servers.json ./mcp_servers.json
COPY --from=web /backend/static ./static
ARG FRIDAY_VERSION=dev
ENV FRIDAY_VERSION=$FRIDAY_VERSION STATIC_DIR=/srv/static
EXPOSE 8670
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request as u;u.urlopen('http://127.0.0.1:8670/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8670", "--ws-max-size", "20971520", "--proxy-headers", "--forwarded-allow-ips", "*"]
