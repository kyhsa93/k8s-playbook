#!/usr/bin/env bash
# Verifies harness/check_autoscaling.py gives the expected PASS/FAIL verdict
# across its good/bad fixtures (catalog items 18-19).
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

check "requests/bad (target has no resources.requests)"  fail python3 harness/check_autoscaling.py requests fixtures/autoscaling/hpa-no-requests-bad.yaml
check "requests/good (target has resources.requests)"    pass python3 harness/check_autoscaling.py requests fixtures/autoscaling/hpa-no-requests-good.yaml
check "minmax/bad (minReplicas == maxReplicas)"           fail python3 harness/check_autoscaling.py minmax fixtures/autoscaling/hpa-minmax-bad.yaml
check "minmax/good (minReplicas < maxReplicas)"           pass python3 harness/check_autoscaling.py minmax fixtures/autoscaling/hpa-minmax-good.yaml

exit $fail
