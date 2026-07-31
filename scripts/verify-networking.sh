#!/usr/bin/env bash
# Verifies harness/check_networking.py gives the expected PASS/FAIL verdict
# across its good/bad fixtures (catalog items 16-17).
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

check "netpol/bad (no NetworkPolicy)"    fail python3 harness/check_networking.py netpol fixtures/networking/netpol-bad.yaml
check "netpol/good (NetworkPolicy present)" pass python3 harness/check_networking.py netpol fixtures/networking/netpol-good.yaml
check "tls/bad (no spec.tls)"            fail python3 harness/check_networking.py tls fixtures/networking/ingress-tls-bad.yaml
check "tls/good (spec.tls present)"      pass python3 harness/check_networking.py tls fixtures/networking/ingress-tls-good.yaml

exit $fail
