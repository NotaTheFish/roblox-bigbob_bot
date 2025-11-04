#!/bin/sh
set -euo pipefail

: "${PORT:=10000}"
: "${SERVICE_ROLE:=bot}"

if [ "$SERVICE_ROLE" = "backend" ]; then
  exec uvicorn backend.main:app --host 0.0.0.0 --port "$PORT"
else
  exec gunicorn bot.web_server:app --bind "0.0.0.0:${PORT}"
fi