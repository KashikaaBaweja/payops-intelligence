#!/bin/sh
set -eu

python -m apps.api.boot
exec uvicorn apps.api.main:app \
  --host "${PAYOPS_API_HOST:-0.0.0.0}" \
  --port "${PAYOPS_API_PORT:-8000}"
