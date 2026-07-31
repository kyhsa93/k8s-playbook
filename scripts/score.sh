#!/usr/bin/env bash
# Aggregate scorer for the AI manifest-authoring benchmark (docs/benchmark.md).
# Runs every catalog check that can be scored from a single rendered manifest
# snapshot (items 1-6, 9, 10, 14-19), plus item 12 if a Kargo Stage pipeline
# file is also given, plus item 13 if a new app-registration file is also
# given, plus items 7-8 if --config <dir> is given, against one submission and
# reports a combined PASS/FAIL/N-A result. Unlike scripts/verify-*.sh (which
# assert known fixtures pass/fail), this scores an arbitrary new manifest --
# deliberately not wired into scripts/verify-all.sh.
set -uo pipefail
cd "$(dirname "$0")/.."

config_dir=""
positional=()
while [ $# -gt 0 ]; do
  case "$1" in
    --config)
      config_dir="$2"
      shift 2
      ;;
    *)
      positional+=("$1")
      shift
      ;;
  esac
done
set -- "${positional[@]}"

if [ $# -lt 1 ] || [ $# -gt 3 ]; then
  echo "usage: score.sh <manifest.yaml|-> [promotion-pipeline.yaml] [apps-registration.yaml] [--config <dir>]" >&2
  exit 2
fi

file="$1"
promotion_file="${2:-}"
apps_file="${3:-}"
tmpinput=""
apps_combined=""
config_tmpfiles=()
if [ "$file" = "-" ]; then
  tmpinput="$(mktemp)"
  cat > "$tmpinput"
  file="$tmpinput"
fi
cleanup() {
  [ -n "$tmpinput" ] && rm -f "$tmpinput"
  [ -n "$apps_combined" ] && rm -f "$apps_combined"
  [ "${#config_tmpfiles[@]}" -gt 0 ] && rm -f "${config_tmpfiles[@]}"
  return 0
}
trap cleanup EXIT

passed=0
failed=0
na=0

score() {
  local label="$1"
  shift
  local out
  out="$(mktemp)"
  "$@" > "$out" 2>&1
  local status=$?
  local firstline
  firstline="$(head -1 "$out")"
  if [ "$status" -eq 0 ]; then
    echo "[PASS] $label -- $firstline"
    passed=$((passed + 1))
  elif [[ "$firstline" =~ ^no\ .*\ found\ in\  ]]; then
    echo "[N/A]  $label -- $firstline"
    na=$((na + 1))
  else
    echo "[FAIL] $label -- $firstline"
    failed=$((failed + 1))
  fi
  rm -f "$out"
}

score "workload (items 1-6)"        python3 harness/check_workload.py "$file"
score "secrets/exposure (item 9)"   python3 harness/check_secrets.py exposure "$file"
score "secrets/plaintext (item 10)" python3 harness/check_secrets.py plaintext "$file"
score "namespace (item 14)"         python3 harness/check_namespace_tenancy.py namespace "$file"
score "rbac (item 15)"              python3 harness/check_namespace_tenancy.py rbac "$file"
score "netpol (item 16)"            python3 harness/check_networking.py netpol "$file"
score "ingress-tls (item 17)"       python3 harness/check_networking.py tls "$file"
score "hpa-requests (item 18)"      python3 harness/check_autoscaling.py requests "$file"
score "hpa-minmax (item 19)"        python3 harness/check_autoscaling.py minmax "$file"

if [ -n "$promotion_file" ]; then
  score "promotion (item 12)"       python3 harness/check_gitops_state.py promotion "$promotion_file"
fi

if [ -n "$apps_file" ]; then
  # check_apps judges tree membership across the whole set it's given, not the
  # new app specifically -- fixtures/benchmark/apps-context.yaml is deliberately
  # a single dependsOn-less Kustomization so PASS only happens if the agent's
  # own new resource correctly joins it (see that file's own comment).
  apps_combined="$(mktemp)"
  { cat fixtures/benchmark/apps-context.yaml; echo "---"; cat "$apps_file"; } > "$apps_combined"
  score "apps (item 13)"             python3 harness/check_gitops_state.py apps "$apps_combined"
fi

if [ -n "$config_dir" ]; then
  if [ -f "$config_dir/Chart.yaml" ]; then
    # Helm chart + per-env values.yaml overrides -- render each env, then score
    # env-parity on the renders (item 7) and values-bloat on the raw values
    # files directly (item 8, no rendering needed -- it's a schema-size check).
    env_renders=()
    for env in dev staging prod; do
      rendered="$(mktemp)"
      config_tmpfiles+=("$rendered")
      helm template "$config_dir" -f "$config_dir/values-$env.yaml" > "$rendered"
      env_renders+=("$rendered")
    done
    score "env-parity (item 7)"      python3 harness/check_config_mgmt.py env-parity "${env_renders[@]}"
    score "values-bloat (item 8)"    python3 harness/check_config_mgmt.py values-bloat \
      "$config_dir/values.yaml" "$config_dir/values-dev.yaml" "$config_dir/values-staging.yaml" "$config_dir/values-prod.yaml"
  elif [ -d "$config_dir/overlays/dev" ]; then
    # Kustomize base + overlays/{dev,staging,prod} -- item 8 (values-bloat) has
    # no Kustomize equivalent (there's no values.yaml schema to measure), so
    # only item 7 is scored for this submission shape.
    env_renders=()
    for env in dev staging prod; do
      rendered="$(mktemp)"
      config_tmpfiles+=("$rendered")
      kustomize build "$config_dir/overlays/$env" > "$rendered"
      env_renders+=("$rendered")
    done
    score "env-parity (item 7)"      python3 harness/check_config_mgmt.py env-parity "${env_renders[@]}"
  else
    echo "error: --config $config_dir has neither Chart.yaml (Helm) nor overlays/dev/ (Kustomize)" >&2
    exit 2
  fi
fi

applicable=$((passed + failed))
echo
echo "Score: $passed/$applicable applicable checks passed ($na N/A excluded)"

[ "$failed" -eq 0 ]
