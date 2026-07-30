#!/usr/bin/env bash
# Validates harness/check_namespace_tenancy.py against real kustomize/helm renders,
# including a real public chart's conditional RBAC templating (closes GitHub issue #3).
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

# namespace: real Kustomize `namespace:` transformer
check "namespace/kustomize-good (namespace: payment)" pass bash -c \
  "kustomize build fixtures/namespace-tenancy/kustomize-real/overlays/good | python3 harness/check_namespace_tenancy.py namespace -"
check "namespace/kustomize-bad (namespace: default)" fail bash -c \
  "kustomize build fixtures/namespace-tenancy/kustomize-real/overlays/bad | python3 harness/check_namespace_tenancy.py namespace -"

# namespace: real Helm .Release.Namespace (via -n flag, or its absence)
check "namespace/helm-good (helm template -n payment)" pass bash -c \
  "helm template fixtures/namespace-tenancy/helm-real -n payment | python3 harness/check_namespace_tenancy.py namespace -"
check "namespace/helm-bad (helm template with no -n, defaults to 'default')" fail bash -c \
  "helm template fixtures/namespace-tenancy/helm-real | python3 harness/check_namespace_tenancy.py namespace -"

# rbac: real ingress-nginx chart's conditional ClusterRole vs Role/RoleBinding templating
check "rbac/real-chart-cluster-wide (rbac.scope=false, the chart default)" fail \
  python3 harness/check_namespace_tenancy.py rbac fixtures/namespace-tenancy/real-world/rbac-cluster-wide.yaml
check "rbac/real-chart-namespaced (rbac.scope=true)" pass \
  python3 harness/check_namespace_tenancy.py rbac fixtures/namespace-tenancy/real-world/rbac-namespaced.yaml

exit $fail
