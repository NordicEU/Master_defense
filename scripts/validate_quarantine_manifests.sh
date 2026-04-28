#!/usr/bin/env bash
set -euo pipefail

K8S_DIR="${K8S_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../infra/k8s" && pwd)}"

echo "==> Validating quarantine Kubernetes manifests in: ${K8S_DIR}"
cd "${K8S_DIR}"

echo
echo "==> ConfigMap"
kubectl apply --dry-run=client -f quarantine-configmap.yaml

echo
echo "==> PVC"
kubectl apply --dry-run=client -f quarantine-pvc.yaml

echo
echo "==> Service"
kubectl apply --dry-run=client -f quarantine-service.yaml

echo
echo "==> Deployment"
kubectl apply --dry-run=client -f quarantine-deployment.yaml

echo
echo "==> NetworkPolicy"
kubectl apply --dry-run=client -f quarantine-networkpolicy.yaml

echo
echo "==> PodDisruptionBudget"
kubectl apply --dry-run=client -f quarantine-poddisruptionbudget.yaml

echo
echo "==> RBAC"
kubectl apply --dry-run=client -f quarantine-role.yaml

echo
echo "==> Optional ServiceMonitor"
if kubectl apply --dry-run=client -f quarantine-servicemonitor.yaml >/dev/null 2>&1; then
  echo "ServiceMonitor validated successfully."
else
  echo "ServiceMonitor skipped: CRD monitoring.coreos.com/v1 may not be installed in this cluster."
fi

echo
echo "Quarantine manifest validation completed successfully."
