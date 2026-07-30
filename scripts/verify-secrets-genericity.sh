#!/usr/bin/env bash
# Validates harness/check_secrets.py against real kustomize/helm renders and real
# SealedSecret/ExternalSecret schemas (closes GitHub issue #2).
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/.tools/bin:$PATH"

fail=0
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

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

# exposure against real kustomize build output
check "exposure/kustomize-bad" fail bash -c "kustomize build fixtures/secrets/kustomize-real/bad | python3 harness/check_secrets.py exposure -"
check "exposure/kustomize-good" pass bash -c "kustomize build fixtures/secrets/kustomize-real/good | python3 harness/check_secrets.py exposure -"

# exposure against real helm template output
check "exposure/helm-bad" fail bash -c "helm template fixtures/secrets/helm-real | python3 harness/check_secrets.py exposure -"
check "exposure/helm-good" pass bash -c "helm template fixtures/secrets/helm-real -f fixtures/secrets/helm-real/values-good.yaml | python3 harness/check_secrets.py exposure -"

# plaintext against real SealedSecret (bitnami-labs) and ExternalSecret (external-secrets.io) schemas
check "plaintext/sealed-secret (real schema)"    pass python3 harness/check_secrets.py plaintext fixtures/secrets/plaintext-good.yaml
check "plaintext/external-secret (real schema)"  pass python3 harness/check_secrets.py plaintext fixtures/secrets/plaintext-good-externalsecret.yaml
check "plaintext/raw-secret-still-caught"        fail python3 harness/check_secrets.py plaintext fixtures/secrets/plaintext-bad.yaml

exit $fail
