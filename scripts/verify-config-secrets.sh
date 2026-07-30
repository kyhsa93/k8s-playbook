#!/usr/bin/env bash
# Verifies harness/check_config_mgmt.py and harness/check_secrets.py give the
# expected PASS/FAIL verdict across their good/bad fixtures (catalog items 7-10).
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

check "env-parity/bad (hardcoded across envs)" fail python3 harness/check_config_mgmt.py env-parity \
  fixtures/config-mgmt/env-parity/bad/dev.yaml fixtures/config-mgmt/env-parity/bad/staging.yaml fixtures/config-mgmt/env-parity/bad/prod.yaml
check "env-parity/good (varies per env)" pass python3 harness/check_config_mgmt.py env-parity \
  fixtures/config-mgmt/env-parity/good/dev.yaml fixtures/config-mgmt/env-parity/good/staging.yaml fixtures/config-mgmt/env-parity/good/prod.yaml

check "values-bloat/bad (god values file)" fail python3 harness/check_config_mgmt.py values-bloat \
  fixtures/config-mgmt/values-bloat/bad/values.yaml fixtures/config-mgmt/values-bloat/bad/values-dev.yaml \
  fixtures/config-mgmt/values-bloat/bad/values-staging.yaml fixtures/config-mgmt/values-bloat/bad/values-prod.yaml
check "values-bloat/good (used proportionally)" pass python3 harness/check_config_mgmt.py values-bloat \
  fixtures/config-mgmt/values-bloat/good/values.yaml fixtures/config-mgmt/values-bloat/good/values-dev.yaml \
  fixtures/config-mgmt/values-bloat/good/values-staging.yaml fixtures/config-mgmt/values-bloat/good/values-prod.yaml

check "secrets/exposure-bad"  fail python3 harness/check_secrets.py exposure fixtures/secrets/exposure-bad.yaml
check "secrets/exposure-good" pass python3 harness/check_secrets.py exposure fixtures/secrets/exposure-good.yaml
check "secrets/plaintext-bad"  fail python3 harness/check_secrets.py plaintext fixtures/secrets/plaintext-bad.yaml
check "secrets/plaintext-good" pass python3 harness/check_secrets.py plaintext fixtures/secrets/plaintext-good.yaml

exit $fail
