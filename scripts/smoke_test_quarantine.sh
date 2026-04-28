#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8003}"

echo "==> Health check"
curl -s "${BASE_URL}/health"
echo
echo

echo "==> Create quarantine case"
CREATE_RESPONSE=$(curl -s -X POST "${BASE_URL}/quarantine" \
  -H "Content-Type: application/json" \
  -d '{
    "submission": {
      "submission_id": "smoke-script-submission-001",
      "source": "dataset_replay",
      "payload_type": "tax_document",
      "received_at": "2026-04-09T00:00:00Z",
      "correlation_id": null,
      "schema_version": "v1",
      "payload": {
        "data": {
          "document_type": "SKATTEPLIKT_2025",
          "person_id": "11111111111",
          "partsnummer": "3000011111",
          "inntektsaar": "2025",
          "fields": {
            "skatteplikt_til_norge": "true"
          }
        }
      }
    },
    "normalized_payload": {
      "document_type": "SKATTEPLIKT_2025",
      "person_id": "11111111111",
      "partsnummer": "3000011111",
      "inntektsaar": "2025",
      "fields": {
        "skatteplikt_til_norge": "true"
      }
    },
    "risk_assessment": {
      "assessment_id": "risk-smoke-script-001",
      "rule_score": 0.35,
      "statistical_score": 0.30,
      "context_score": 0.82,
      "semantic_score": 0.10,
      "total_score": 0.52,
      "confidence": 0.84,
      "findings": [],
      "semantic_reasoning": "Semantic layer did not override containment.",
      "recommended_action": "REVIEW",
      "assessed_at": "2026-04-09T00:00:00Z"
    },
    "decision_result": {
      "decision_id": "decision-smoke-script-001",
      "action": "QUARANTINE",
      "policy_version": "v_final",
      "reasons": [
        "context_mismatch",
        "policy_containment"
      ],
      "decided_at": "2026-04-09T00:00:00Z"
    }
  }')

echo "${CREATE_RESPONSE}"
echo
echo

CASE_ID=$(python3 - <<'PY' "$CREATE_RESPONSE"
import json, sys
data = json.loads(sys.argv[1])
print(data["case_id"])
PY
)

echo "==> Extracted case_id: ${CASE_ID}"
echo
echo

echo "==> List quarantine cases"
curl -s "${BASE_URL}/quarantine"
echo
echo

echo "==> Get created case"
curl -s "${BASE_URL}/quarantine/${CASE_ID}"
echo
echo

echo "==> Update case state to UNDER_REVIEW"
curl -s -X POST "${BASE_URL}/quarantine/${CASE_ID}/state" \
  -H "Content-Type: application/json" \
  -d '{
    "new_state": "UNDER_REVIEW",
    "actor": "smoke_test",
    "message": "Smoke test state transition.",
    "details": {
      "source": "smoke_test_quarantine.sh"
    }
  }'
echo
echo

echo "==> Get updated case"
curl -s "${BASE_URL}/quarantine/${CASE_ID}"
echo
echo

echo "==> Metrics JSON"
curl -s "${BASE_URL}/quarantine/metrics"
echo
echo

echo "==> Metrics Prometheus"
curl -s "${BASE_URL}/metrics"
echo
echo

echo "Smoke test completed successfully."
