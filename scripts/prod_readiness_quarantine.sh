#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${BASE_DIR}"

echo "==> Production readiness check: quarantine component"
echo

if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

echo "==> Running quarantine-focused pytest suite"
pytest tests/test_quarantine_policy.py -q
pytest tests/test_audit_logger.py -q
pytest tests/test_quarantine_metrics.py -q
pytest tests/test_quarantine_service.py -q
echo

echo "==> Running full pytest suite"
pytest tests -q
echo

echo "==> Running quarantine smoke test"
./scripts/smoke_test_quarantine.sh
echo

echo "==> Validating Kubernetes manifests"
./scripts/validate_quarantine_manifests.sh
echo

echo "==> Optional Docker health check"
if docker ps --format '{{.Names}}' | grep -q '^quarantine-test$'; then
  echo "Found running container: quarantine-test"
  curl -s http://127.0.0.1:8015/health
  echo
else
  echo "Skipping Docker health check: container 'quarantine-test' is not running."
fi
echo

echo "Quarantine component production readiness check completed successfully."
