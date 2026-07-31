#!/usr/bin/env bash
# Single entry point running every harness verification script in this repo.
# Add a new script's basename here whenever a new harness/genericity pass is added.
set -uo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/.tools/bin:$PATH"

SCRIPTS=(
  scripts/verify-genericity.sh
  scripts/verify-gitops-state.sh
  scripts/verify-config-secrets.sh
  scripts/verify-namespace-tenancy.sh
  scripts/verify-config-mgmt-genericity.sh
  scripts/verify-secrets-genericity.sh
  scripts/verify-namespace-tenancy-genericity.sh
  scripts/verify-live-argocd.sh
  scripts/verify-networking.sh
  scripts/verify-networking-genericity.sh
  scripts/verify-autoscaling.sh
  scripts/verify-autoscaling-genericity.sh
)

overall=0
for script in "${SCRIPTS[@]}"; do
  echo "=== $script ==="
  if "$script"; then
    echo "--- $script: PASS ---"
  else
    echo "--- $script: FAIL ---"
    overall=1
  fi
  echo
done

if [ "$overall" -eq 0 ]; then
  echo "ALL SCRIPTS PASSED"
else
  echo "ONE OR MORE SCRIPTS FAILED"
fi
exit $overall
