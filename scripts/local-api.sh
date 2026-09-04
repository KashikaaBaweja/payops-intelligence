#!/bin/sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -f .venv/bin/activate ]; then
  echo "Create a venv first: python3 -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]'" >&2
  exit 1
fi
# shellcheck disable=SC1091
. .venv/bin/activate
if [ ! -f .env ]; then
  cp .env.example .env
fi
payops-seed
export PYTHONPATH="${PYTHONPATH:-}:packages:."
exec uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
