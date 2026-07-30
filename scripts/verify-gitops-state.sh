#!/usr/bin/env bash
# Verifies harness/check_gitops_state.py gives the expected PASS/FAIL verdict across
# fixtures modeling real Argo CD, Flux, and Kargo conventions (not one invented schema) --
# proving the drift/promotion/apps checks generalize across tools, the same way
# verify-genericity.sh does for the workload harness.
set -euo pipefail
cd "$(dirname "$0")/.."

fail=0

check() {
  local label="$1" expect="$2"
  shift 2
  local out
  out="$(mktemp)"
  if python3 harness/check_gitops_state.py "$@" > "$out" 2>&1; then
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

check "drift/good (real kind cluster dump)"      pass drift fixtures/gitops/drift/declared.yaml fixtures/gitops/drift/live-good.yaml
check "drift/bad (real kind cluster dump)"       fail drift fixtures/gitops/drift/declared.yaml fixtures/gitops/drift/live-bad.yaml
check "promotion/good (real Kargo Stage schema)" pass promotion fixtures/gitops/promotion/good.yaml
check "promotion/bad (real Kargo Stage schema)"  fail promotion fixtures/gitops/promotion/bad.yaml
check "apps/argocd-directory-recursion"          pass apps fixtures/gitops/apps/good-argocd-recurse.yaml
check "apps/flux-dependson-tree"                 pass apps fixtures/gitops/apps/good-flux-dependson.yaml
check "apps/argocd-applicationset"               pass apps fixtures/gitops/apps/good-applicationset.yaml
check "apps/bad (registered one by one)"         fail apps fixtures/gitops/apps/bad.yaml

exit $fail
