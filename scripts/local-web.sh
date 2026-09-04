#!/bin/sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
cd "$ROOT/apps/web"
if [ ! -d node_modules ]; then
  npm install
fi
exec npm run dev
