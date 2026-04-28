#!/usr/bin/env bash

set -euo pipefail

OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-llama3}"
RUNTIME_DIR="${RUNTIME_DIR:-runtime}"

mkdir -p "$RUNTIME_DIR"

if ! command -v ollama >/dev/null 2>&1; then
  cat >&2 <<EOF
Ollama is not installed on this machine.

Install it on the VM first:
  curl -fsSL https://ollama.com/install.sh | sh

Then rerun:
  ./scripts/ensure_ollama.sh
EOF
  exit 1
fi

if ! curl -fsS "$OLLAMA_HOST/api/tags" >/dev/null 2>&1; then
  echo "Starting local Ollama server on $OLLAMA_HOST"
  nohup ollama serve > "$RUNTIME_DIR/logs_ollama.out" 2>&1 &
  sleep 3
fi

if ! curl -fsS "$OLLAMA_HOST/api/tags" >/dev/null 2>&1; then
  echo "Ollama did not become reachable at $OLLAMA_HOST" >&2
  echo "Check $RUNTIME_DIR/logs_ollama.out" >&2
  exit 1
fi

if ! ollama list | awk 'NR > 1 { print $1 }' | grep -Eq "^${OLLAMA_MODEL}(:|$)"; then
  echo "Pulling Ollama model: $OLLAMA_MODEL"
  ollama pull "$OLLAMA_MODEL"
fi

echo "Ollama ready: $OLLAMA_HOST using model $OLLAMA_MODEL"
