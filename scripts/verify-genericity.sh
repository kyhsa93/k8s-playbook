#!/usr/bin/env bash
# Verifies harness/check_workload.py gives the same PASS/FAIL verdict across
# raw manifest, Kustomize, and Helm renders of the same fixture — proving the
# harness checks final rendered objects rather than assuming one templating tool.
set -euo pipefail
cd "$(dirname "$0")/.."

fail=0

check() {
  local label="$1" expect="$2"
  shift 2
  local out
  out="$(mktemp)"
  if "$@" | python3 harness/check_workload.py - > "$out" 2>&1; then
    actual=pass
  else
    actual=fail
  fi
  if [ "$actual" = "$expect" ]; then
    echo "OK   $label ($actual as expected)"
  else
    echo "FAIL $label: expected $expect, got $actual"
    cat "$out"
    fail=1
  fi
  rm -f "$out"
}

check "raw/bad"        fail cat fixtures/raw/bad-deployment.yaml
check "raw/good"       pass cat fixtures/raw/good-deployment.yaml
check "kustomize/bad"  fail kustomize build fixtures/kustomize/bad
check "kustomize/good" pass kustomize build fixtures/kustomize/good
check "helm/bad"       fail helm template fixtures/helm/payment-api
check "helm/good"      pass helm template fixtures/helm/payment-api -f fixtures/helm/payment-api/values-good.yaml

exit $fail
