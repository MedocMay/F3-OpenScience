# Open-Sci 后端镜像(本地网关 + 云网关共用;compose 里用 command 选择入口)
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm curl && rm -rf /var/lib/apt/lists/*
COPY . /app
# 核心零依赖;云端可选依赖按需装(Postgres/Redis/加密)
RUN pip install --no-cache-dir jsonschema cryptography "psycopg[binary]" redis && \
    (cd orchestrator-ts && npm i --omit=dev || true)
ENV PORT=8080
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD curl -sf http://localhost:${PORT}/healthz || exit 1
CMD ["python3", "deploy/gateway.py"]
