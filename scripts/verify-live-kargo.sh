#!/usr/bin/env bash
# Validates harness/check_gitops_state.py promotion against a genuinely admitting
# Kargo controller (not just the documented Stage CRD schema) -- reruns the checks
# against fixtures captured live from a real Kargo v1.11.0 instance in a disposable
# kind cluster. See fixtures/gitops/promotion/live-kargo-*.yaml for how each was
# captured and examples/kargo-live-validation/ for how to reproduce it from scratch.
set -euo pipefail
cd "$(dirname "$0")/.."

fail=0

check() {
  local label="$1" expect="$2"
  shift 2
  local out
  out="$(mktemp)"
  if "$@" > "$out" 2>&1; then
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

check "promotion/live-kargo-full (every stage has a verification gate)" pass \
  python3 harness/check_gitops_state.py promotion fixtures/gitops/promotion/live-kargo-full.yaml
check "promotion/live-kargo-no-gate (prod's verification removed via a real patch)" fail \
  python3 harness/check_gitops_state.py promotion fixtures/gitops/promotion/live-kargo-no-gate.yaml

exit $fail
