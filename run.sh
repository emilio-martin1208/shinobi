#!/usr/bin/env bash
# Start the Shinobi dev server with live reload.
# Usage: ./run.sh [port]   (defaults to 8000)
set -euo pipefail

PORT="${1:-8000}"

if [ ! -f .env ]; then
  echo "warning: no .env found — copy .env.example to .env and add your keys." >&2
fi

exec uvicorn main:app --reload --host 0.0.0.0 --port "$PORT"
