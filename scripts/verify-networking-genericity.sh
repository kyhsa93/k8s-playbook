#!/usr/bin/env bash
# Validates harness/check_networking.py against real kustomize/helm renders and
# the real ingress-nginx chart's NetworkPolicy toggle.
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

# tls: real Kustomize JSON6902 patch adding spec.tls
check "tls/kustomize-good (patch adds tls)" pass bash -c \
  "kustomize build fixtures/networking/kustomize-real/overlays/good | python3 harness/check_networking.py tls -"
check "tls/kustomize-bad (no patch)" fail bash -c \
  "kustomize build fixtures/networking/kustomize-real/overlays/bad | python3 harness/check_networking.py tls -"

# tls: real Helm conditional block
check "tls/helm-good (tls.enabled=true)" pass bash -c \
  "helm template fixtures/networking/helm-real -f fixtures/networking/helm-real/values-good.yaml | python3 harness/check_networking.py tls -"
check "tls/helm-bad (tls.enabled=false, the chart default)" fail bash -c \
  "helm template fixtures/networking/helm-real | python3 harness/check_networking.py tls -"

# netpol: real ingress-nginx chart's controller.networkPolicy.enabled toggle
check "netpol/real-chart-disabled (the chart default)" fail \
  python3 harness/check_networking.py netpol fixtures/networking/real-world/netpol-disabled.yaml
check "netpol/real-chart-enabled" pass \
  python3 harness/check_networking.py netpol fixtures/networking/real-world/netpol-enabled.yaml

exit $fail
