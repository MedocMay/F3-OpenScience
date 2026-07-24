#!/usr/bin/env bash
# 一键本地部署(无需 Docker)。起 global 服务 + 网关,数据全留本地。
# 用法:bash deploy/run-local.sh   然后浏览器/HTTP 访问 http://localhost:8080
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data
[ -f deploy/.env ] && set -a && . deploy/.env && set +a || echo "(未找到 deploy/.env,用默认值;可 cp deploy/.env.example deploy/.env)"
command -v python3 >/dev/null || { echo "需要 python3"; exit 1; }

echo "· 启动 global 记忆服务 :8090"
OPENSCI_GLOBAL_DB="${OPENSCI_GLOBAL_DB:-./data/global.db}" PORT=8090 python3 deploy/global_service.py &
GPID=$!
echo "· 启动网关 :${PORT:-8080}"
OPENSCI_GLOBAL_URL="${OPENSCI_GLOBAL_URL:-http://localhost:8090}" \
OPENSCI_DB="${OPENSCI_DB:-./data/gateway_mem.db}" PORT="${PORT:-8080}" python3 deploy/gateway.py &
WPID=$!
trap 'kill $GPID $WPID 2>/dev/null' EXIT
sleep 2
echo ""
echo "✓ F3-OpenScience 本地已启动:"
echo "    网关   http://localhost:${PORT:-8080}   (POST /v1/runs 开始一次研究)"
echo "    global http://localhost:8090"
echo "    数据都在 ./data/(SQLite);模型=${OPENSCI_MODEL:-未设,默认本地}"
echo "  Ctrl-C 结束。"
wait
