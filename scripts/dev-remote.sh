#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python"
cd "$PROJECT_DIR"

if [[ ! -x "$PYTHON" ]]; then
    echo ".venv가 없습니다. 먼저 python3 -m venv .venv를 실행하세요." >&2
    exit 1
fi

REMOTE_DB_HOST="$($PYTHON - <<'PY'
from dotenv import dotenv_values

value = dotenv_values(".env").get("DB_HOST")
if not value:
    raise SystemExit(".env에 DB_HOST가 없습니다.")
print(value)
PY
)"
REMOTE_DB_PORT="$($PYTHON - <<'PY'
from dotenv import dotenv_values

value = dotenv_values(".env").get("DB_PORT", "3306")
print(value)
PY
)"
LOCAL_DB_PORT=13306

ssh -o ExitOnForwardFailure=yes \
    -N \
    -L "${LOCAL_DB_PORT}:${REMOTE_DB_HOST}:${REMOTE_DB_PORT}" \
    cloud-api &

TUNNEL_PID=$!

cleanup() {
    kill "$TUNNEL_PID" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

sleep 1
if ! kill -0 "$TUNNEL_PID" 2>/dev/null; then
    echo "SSH DB 터널을 열지 못했습니다." >&2
    exit 1
fi

DB_HOST=127.0.0.1 \
DB_PORT="$LOCAL_DB_PORT" \
# 메모리 기반 token 폐기 목록을 사용하므로 단일 프로세스로 실행한다.
./.venv/bin/uvicorn app.main:app
