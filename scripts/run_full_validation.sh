#!/usr/bin/env bash
set -e

cd ~/master_defense

echo "== COMPILE CHECK =="
python3 -m py_compile \
  shared/models/decision.py \
  shared/models/risk.py \
  shared/models/quarantine_case.py \
  shared/models/containment_advisory.py \
  shared/policies/decision_policy.py \
  shared/policies/quarantine_policy.py \
  shared/policies/containment_state_policy.py \
  apps/input_app/app.py \
  services/decision_service/app.py \
  services/gateway_service/app.py \
  services/review_service/app.py \
  services/deception_service/app.py \
  services/defer_service/app.py \
  services/quarantine_service/app.py \
  scripts/test_routing_matrix.py \
  scripts/test_containment_workflow.py \
  scripts/test_minefield_workflow.py \
  scripts/test_honeypot_to_containment.py \
  scripts/test_deceiver_to_minefield.py

echo "== RESTART SERVICES =="
./stop_all.sh
./start_all.sh

echo "== ROUTING MATRIX =="
./.venv/bin/python scripts/test_routing_matrix.py

echo "== CONTAINMENT WORKFLOW =="
./.venv/bin/python scripts/test_containment_workflow.py

echo "== MINEFIELD WORKFLOW =="
./.venv/bin/python scripts/test_minefield_workflow.py

echo "== HONEYPOT -> CONTAINMENT =="
./.venv/bin/python scripts/test_honeypot_to_containment.py

echo "== DECEIVER -> MINEFIELD =="
./.venv/bin/python scripts/test_deceiver_to_minefield.py

echo "== FULL VALIDATION COMPLETE =="
