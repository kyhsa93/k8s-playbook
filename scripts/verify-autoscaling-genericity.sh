#!/usr/bin/env bash
# Validates harness/check_autoscaling.py against the real ingress-nginx chart's
# controller.autoscaling toggle and its default container resource requests.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/.tools/bin:$PATH"

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

check "requests/real-chart-good (default controller.resources.requests kept)" pass \
  python3 harness/check_autoscaling.py requests fixtures/autoscaling/real-world/hpa-enabled-with-requests.yaml
check "requests/real-chart-bad (controller.resources.requests stripped)" fail \
  python3 harness/check_autoscaling.py requests fixtures/autoscaling/real-world/hpa-enabled-no-requests.yaml
check "minmax/real-chart-good (default minReplicas=1, maxReplicas=11)" pass \
  python3 harness/check_autoscaling.py minmax fixtures/autoscaling/real-world/hpa-enabled-with-requests.yaml
check "minmax/real-chart-bad (minReplicas=maxReplicas=3)" fail \
  python3 harness/check_autoscaling.py minmax fixtures/autoscaling/real-world/hpa-minmax-equal.yaml

exit $fail
