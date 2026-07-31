#!/usr/bin/env bash
# Validates harness/check_gitops_state.py apps's has_flux_dependency_tree signal
# against a genuinely reconciling Flux controller (not just the CRD schema) --
# reruns the checks against fixtures captured live from a real Flux v2 instance in a
# disposable kind cluster. See fixtures/gitops/apps/live-flux-*.yaml for how each was
# captured and examples/flux-live-validation/ for how to reproduce it from scratch.
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

check "apps/live-flux-dependson-full (root + dependents included)" pass \
  python3 harness/check_gitops_state.py apps fixtures/gitops/apps/live-flux-dependson-full.yaml
check "apps/live-flux-dependson-children-only (root excluded, documents a real caveat)" fail \
  python3 harness/check_gitops_state.py apps fixtures/gitops/apps/live-flux-dependson-children-only.yaml

exit $fail
