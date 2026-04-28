#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")"
source .venv/bin/activate

mkdir -p runtime

export OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-llama3}"

./scripts/ensure_ollama.sh

pkill -f "uvicorn services.intake_service.app:app" || true
pkill -f "uvicorn services.decision_service.app:app" || true
pkill -f "uvicorn services.quarantine_service.app:app" || true
pkill -f "uvicorn apps.business_app.app:app" || true
pkill -f "uvicorn services.gateway_service.app:app" || true
pkill -f "uvicorn analysis.rule_engine.app:app" || true
pkill -f "uvicorn analysis.context_validator.app:app" || true
pkill -f "uvicorn analysis.anomaly_scorer.app:app" || true
pkill -f "uvicorn analysis.semantic_assist.app:app" || true
pkill -f "uvicorn apps.input_app.app:app" || true
pkill -f "uvicorn services.review_service.app:app" || true
pkill -f "uvicorn services.defer_service.app:app" || true
pkill -f "uvicorn services.deception_service.app:app" || true
pkill -f "uvicorn apps.ops_app.app:app" || true

sleep 2

nohup uvicorn services.intake_service.app:app --host 127.0.0.1 --port 8001 > runtime/logs_intake.out 2>&1 &
nohup uvicorn services.decision_service.app:app --host 127.0.0.1 --port 8002 > runtime/logs_decision.out 2>&1 &
nohup uvicorn services.quarantine_service.app:app --host 127.0.0.1 --port 8003 > runtime/logs_quarantine.out 2>&1 &
nohup uvicorn apps.business_app.app:app --host 127.0.0.1 --port 8004 > runtime/logs_business.out 2>&1 &
nohup uvicorn services.review_service.app:app --host 127.0.0.1 --port 8005 > runtime/logs_review.out 2>&1 &
nohup uvicorn services.defer_service.app:app --host 127.0.0.1 --port 8006 > runtime/logs_defer.out 2>&1 &
nohup uvicorn services.deception_service.app:app --host 127.0.0.1 --port 8007 > runtime/logs_deception.out 2>&1 &
nohup uvicorn services.gateway_service.app:app --host 127.0.0.1 --port 8000 > runtime/logs_gateway.out 2>&1 &
nohup uvicorn analysis.rule_engine.app:app --host 127.0.0.1 --port 8011 > runtime/logs_rule_engine.out 2>&1 &
nohup uvicorn analysis.anomaly_scorer.app:app --host 127.0.0.1 --port 8012 > runtime/logs_anomaly_scorer.out 2>&1 &
nohup uvicorn analysis.context_validator.app:app --host 127.0.0.1 --port 8013 > runtime/logs_context_validator.out 2>&1 &
nohup uvicorn analysis.semantic_assist.app:app --host 127.0.0.1 --port 8014 > runtime/logs_semantic_assist.out 2>&1 &
nohup uvicorn apps.input_app.app:app --host 127.0.0.1 --port 8080 > runtime/logs_input_app.out 2>&1 &
nohup uvicorn apps.ops_app.app:app --host 127.0.0.1 --port 8090 > runtime/logs_ops_app.out 2>&1 &

sleep 2

echo "Started services:"
ss -ltnp | grep -E '8000|8001|8002|8003|8004|8005|8006|8007|8011|8012|8013|8014|8080|8090' || true
