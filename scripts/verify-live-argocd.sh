#!/usr/bin/env bash
# Validates harness/check_gitops_state.py apps against a genuinely reconciling
# Argo CD controller (not just docs/schemas) -- reruns the checks against fixtures
# captured live from a real Argo CD v3.4.5 instance in a disposable kind cluster.
# See fixtures/gitops/apps/live-argocd-*.yaml for how each was captured and
# examples/argocd-live-validation/ for how to reproduce it from scratch.
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

check "apps/live-argocd-appofapps (root + children included)" pass \
  python3 harness/check_gitops_state.py apps fixtures/gitops/apps/live-argocd-appofapps-full.yaml
check "apps/live-argocd-appofapps-children-only (root excluded, documents a real caveat)" fail \
  python3 harness/check_gitops_state.py apps fixtures/gitops/apps/live-argocd-appofapps-children-only.yaml
check "apps/live-argocd-applicationset (real ownerReferences from the controller)" pass \
  python3 harness/check_gitops_state.py apps fixtures/gitops/apps/live-argocd-applicationset-full.yaml

exit $fail
