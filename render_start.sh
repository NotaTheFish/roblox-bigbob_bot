#!/bin/sh
set -euo pipefail

: "${PORT:=10000}"
: "${SERVICE_ROLE:=backend}"

case "$SERVICE_ROLE" in
  backend)
    exec uvicorn backend.main:app --host 0.0.0.0 --port "$PORT"
    ;;
  worker)
    exec python -m bot.main_core
    ;;
  *)
    echo "Unknown SERVICE_ROLE: $SERVICE_ROLE" >&2
    exit 1
    ;;
esac