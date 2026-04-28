#!/usr/bin/env bash

set -euo pipefail

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

sleep 1

echo "Remaining listeners:"
ss -ltnp | grep -E '8000|8001|8002|8003|8004|8005|8006|8007|8011|8012|8013|8014|8080|8090' || true
