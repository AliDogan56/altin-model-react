#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:-localhost}"
case "$PROFILE" in
  local) PROFILE="localhost" ;;
  dev) PROFILE="development" ;;
  prod) PROFILE="production" ;;
esac
if [[ "$PROFILE" != "localhost" && "$PROFILE" != "development" && "$PROFILE" != "production" ]]; then
  echo "Profil localhost, development veya production olmalıdır"
  exit 1
fi

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"
if [ ! -x backend/api-gateway/.venv/bin/python ]; then
  echo "API Gateway ortamı bulunamadı. README kurulum adımlarını uygulayın."
  exit 1
fi
if [ ! -x backend/market-service/.venv/bin/python ]; then
  echo "Market servisi ortamı bulunamadı. README kurulum adımlarını uygulayın."
  exit 1
fi
if [ ! -x backend/model-service/.venv/bin/python ]; then
  echo "Model servisi ortamı bulunamadı. README kurulum adımlarını uygulayın."
  exit 1
fi

backend/market-service/.venv/bin/python backend/market-service/run.py "$PROFILE" &
MARKET_SERVICE_PID=$!
backend/api-gateway/.venv/bin/python backend/api-gateway/run.py "$PROFILE" &
API_GATEWAY_PID=$!
backend/model-service/.venv/bin/python backend/model-service/run.py "$PROFILE" &
MODEL_SERVICE_PID=$!
trap 'kill "$API_GATEWAY_PID" "$MARKET_SERVICE_PID" "$MODEL_SERVICE_PID" 2>/dev/null || true' EXIT INT TERM

NODE_BIN="${NODE_BIN:-$(command -v node || true)}"
if [ -z "$NODE_BIN" ] && [ -x "/Users/alidogan/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node" ]; then
  NODE_BIN="/Users/alidogan/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
fi
if [ -z "$NODE_BIN" ]; then
  echo "Node.js bulunamadı. NODE_BIN ortam değişkeniyle node yolunu belirtin."
  exit 1
fi
cd "$PROJECT_DIR/frontend"
"$NODE_BIN" node_modules/vite/bin/vite.js --mode "$PROFILE"
