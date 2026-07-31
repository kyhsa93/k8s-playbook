#!/usr/bin/env bash
# Aggregate scorer for the AI manifest-authoring benchmark (docs/benchmark.md).
# Runs every catalog check that can be scored from a single rendered manifest
# snapshot (items 1-6, 9, 10, 14-19) against one submission and reports a
# combined PASS/FAIL/N-A result. Unlike scripts/verify-*.sh (which assert known
# fixtures pass/fail), this scores an arbitrary new manifest -- deliberately not
# wired into scripts/verify-all.sh.
set -uo pipefail
cd "$(dirname "$0")/.."

if [ $# -ne 1 ]; then
  echo "usage: score.sh <manifest.yaml|->" >&2
  exit 2
fi

file="$1"
tmpinput=""
if [ "$file" = "-" ]; then
  tmpinput="$(mktemp)"
  cat > "$tmpinput"
  file="$tmpinput"
fi
trap '[ -n "$tmpinput" ] && rm -f "$tmpinput"' EXIT

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

applicable=$((passed + failed))
echo
echo "Score: $passed/$applicable applicable checks passed ($na N/A excluded)"

[ "$failed" -eq 0 ]
