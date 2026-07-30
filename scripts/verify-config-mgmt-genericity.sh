#!/usr/bin/env bash
# Validates harness/check_config_mgmt.py against real kustomize/helm renders and a
# real public Helm chart's values.yaml (closes GitHub issue #1).
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

# env-parity against real kustomize build output
for env in dev staging prod; do
  kustomize build fixtures/config-mgmt/kustomize-real/overlays/$env > "$tmpdir/kz-good-$env.yaml"
  kustomize build fixtures/config-mgmt/kustomize-real/overlays-bad/$env > "$tmpdir/kz-bad-$env.yaml"
done
check "env-parity/kustomize-good (real kustomize build)" pass python3 harness/check_config_mgmt.py env-parity \
  "$tmpdir/kz-good-dev.yaml" "$tmpdir/kz-good-staging.yaml" "$tmpdir/kz-good-prod.yaml"
check "env-parity/kustomize-bad (overlay never patches host/API_URL)" fail python3 harness/check_config_mgmt.py env-parity \
  "$tmpdir/kz-bad-dev.yaml" "$tmpdir/kz-bad-staging.yaml" "$tmpdir/kz-bad-prod.yaml"

# env-parity against real helm template output
for env in dev staging prod; do
  helm template fixtures/config-mgmt/helm-real -f fixtures/config-mgmt/helm-real/values-good-$env.yaml > "$tmpdir/helm-good-$env.yaml"
  helm template fixtures/config-mgmt/helm-real -f fixtures/config-mgmt/helm-real/values-bad-$env.yaml > "$tmpdir/helm-bad-$env.yaml"
done
check "env-parity/helm-good (real helm template)" pass python3 harness/check_config_mgmt.py env-parity \
  "$tmpdir/helm-good-dev.yaml" "$tmpdir/helm-good-staging.yaml" "$tmpdir/helm-good-prod.yaml"
check "env-parity/helm-bad (values files never override apiUrl/ingress.host)" fail python3 harness/check_config_mgmt.py env-parity \
  "$tmpdir/helm-bad-dev.yaml" "$tmpdir/helm-bad-staging.yaml" "$tmpdir/helm-bad-prod.yaml"

# values-bloat against the real public ingress-nginx chart's values.yaml (345 keys)
check "values-bloat/real-world-chart (ingress-nginx, only 6/345 keys ever overridden)" fail python3 harness/check_config_mgmt.py values-bloat \
  fixtures/config-mgmt/values-bloat/real-world/values.yaml \
  fixtures/config-mgmt/values-bloat/real-world/values-dev.yaml \
  fixtures/config-mgmt/values-bloat/real-world/values-staging.yaml \
  fixtures/config-mgmt/values-bloat/real-world/values-prod.yaml

exit $fail
