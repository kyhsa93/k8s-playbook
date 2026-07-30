#!/usr/bin/env bash
# Verifies harness/check_namespace_tenancy.py gives the expected PASS/FAIL
# verdict across its good/bad fixtures (catalog items 14-15).
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

check "namespace/bad (default namespace)" fail python3 harness/check_namespace_tenancy.py namespace fixtures/namespace-tenancy/namespace-bad.yaml
check "namespace/good (team-scoped)"      pass python3 harness/check_namespace_tenancy.py namespace fixtures/namespace-tenancy/namespace-good.yaml
check "rbac/bad (ClusterRoleBinding)"     fail python3 harness/check_namespace_tenancy.py rbac fixtures/namespace-tenancy/rbac-bad.yaml
check "rbac/good (namespaced RoleBinding)" pass python3 harness/check_namespace_tenancy.py rbac fixtures/namespace-tenancy/rbac-good.yaml

exit $fail
