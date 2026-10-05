#!/usr/bin/env bash
# Verifies harness/check_all.py -- the single entrypoint an outside repo uses -- gives
# the expected verdict over a complete manifest set, and that it still does so when the
# manifests arrive by directory, by stdin, or from a Kustomize/Helm render.
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

# The good fixture is split across four files whose objects reference each other
# (PDB, NetworkPolicy and HPA each match a workload declared elsewhere). Passing the
# directory is what proves the inputs get merged before checking rather than checked
# one file at a time.
check "all/good directory"  pass python3 harness/check_all.py fixtures/all/good
check "all/bad directory"   fail python3 harness/check_all.py fixtures/all/bad

# Same manifests over stdin.
check "all/good via stdin"  pass bash -c 'cat fixtures/all/good/*.yaml | python3 harness/check_all.py -'
check "all/bad via stdin"   fail bash -c 'cat fixtures/all/bad/*.yaml | python3 harness/check_all.py -'

# Individual files add up to the same verdict as the directory.
check "all/good file list"  pass python3 harness/check_all.py \
  fixtures/all/good/workload.yaml fixtures/all/good/availability.yaml \
  fixtures/all/good/networking.yaml fixtures/all/good/access.yaml

# A workload-only render trips the checks it has no objects for (no NetworkPolicy is
# itself the item-16 violation), which is the point of the aggregate view: the
# per-item scripts each answer one question and can't see what the render is missing.
check "raw good-deployment (no netpol)" fail python3 harness/check_all.py fixtures/raw/good-deployment.yaml

# An empty input is a usage error, not a pass -- otherwise a typo'd path would look
# like a clean bill of health.
check "empty directory is an error" fail bash -c 'd=$(mktemp -d); python3 harness/check_all.py "$d"'

# A path that doesn't exist must exit 2 (cannot run), not 1 (findings): the action only
# fails the step on findings when fail-on-findings is 'true', but always fails on 2.
check "missing path exits 2" pass bash -c 'python3 harness/check_all.py does-not-exist.yaml 2>/dev/null; [ $? -eq 2 ]'

exit $fail
