#!/usr/bin/env python3
"""Run every rendered-manifest check in this repo against one set of manifests.

The individual harness scripts each take one input and answer one question, which is
right for developing them but wrong for using them: a caller outside this repo would
have to know all seven scripts, their subcommands, and which ones apply. This is the
single entrypoint that knows that instead.

Two things it deliberately does *not* paper over:

- Manifests are merged into one stream before checking. Coverage checks are
  cross-document (a PodDisruptionBudget matching a Deployment in another file, a
  NetworkPolicy covering a namespace declared elsewhere), so checking file-by-file
  would report violations that don't exist.
- Checks whose subject is absent are reported as "n/a", not as a pass. A manifest set
  with no Ingress has not satisfied the Ingress-TLS rule, and printing PASS for it
  would turn "we never looked" into "we looked and it was fine".

Catalog items 7-8 (config management) and 11-13 (GitOps state) are not runnable from a
single rendered manifest set — they compare several environment renders, or read
GitOps controller objects. They are listed as not evaluated at the end of every run
rather than silently omitted; use check_config_mgmt.py / check_gitops_state.py.
"""
import io
import os
import sys
import tempfile

import yaml

import check_autoscaling
import check_namespace_tenancy
import check_networking
import check_secrets
import check_workload

WORKLOADS = {"Deployment", "StatefulSet", "DaemonSet"}

# (label, catalog items, kinds that must be present for the check to mean anything, fn)
# An empty "requires" means the check is meaningful for any manifest set.
CHECKS = [
    ("workload", "1-6", WORKLOADS, check_workload.main),
    ("secrets:exposure", "9", WORKLOADS, check_secrets.check_exposure),
    ("secrets:plaintext", "10", {"Secret"}, check_secrets.check_plaintext),
    ("namespace", "14", set(), check_namespace_tenancy.check_namespace),
    ("rbac", "15", set(), check_namespace_tenancy.check_rbac),
    ("networking:netpol", "16", WORKLOADS, check_networking.check_netpol),
    ("networking:tls", "17", {"Ingress"}, check_networking.check_tls),
    ("autoscaling:requests", "18", {"HorizontalPodAutoscaler"}, check_autoscaling.check_requests),
    ("autoscaling:minmax", "19", {"HorizontalPodAutoscaler"}, check_autoscaling.check_minmax),
]

NOT_EVALUATED = [
    ("config-mgmt", "7-8", "needs two or more environment renders (check_config_mgmt.py)"),
    ("gitops-state", "11-13", "needs GitOps controller objects (check_gitops_state.py)"),
]

YAML_SUFFIXES = (".yaml", ".yml")


def collect_inputs(paths):
    """Read every input into one YAML stream. '-' reads stdin."""
    chunks = []
    for path in paths:
        if path == "-":
            chunks.append(sys.stdin.read())
        elif os.path.isdir(path):
            for root, _, names in os.walk(path):
                for name in sorted(names):
                    if name.endswith(YAML_SUFFIXES):
                        with open(os.path.join(root, name)) as f:
                            chunks.append(f.read())
        else:
            with open(path) as f:
                chunks.append(f.read())
    if not chunks:
        return None
    return "\n---\n".join(chunks)


def kinds_in(stream):
    kinds = set()
    for doc in yaml.safe_load_all(io.StringIO(stream)):
        if not doc:
            continue
        # A List wrapper (what `kubectl get -o yaml` returns) hides its items' kinds.
        if doc.get("kind", "").endswith("List") and isinstance(doc.get("items"), list):
            kinds.update(i.get("kind") for i in doc["items"] if isinstance(i, dict))
        else:
            kinds.add(doc.get("kind"))
    return {k for k in kinds if k}


def main(argv):
    if not argv:
        print("usage: check_all.py <manifest.yaml|dir|-> [more...]", file=sys.stderr)
        return 2

    try:
        stream = collect_inputs(argv)
    except OSError as e:
        # A missing or unreadable path is a broken invocation, not a finding: exit 2
        # so the action fails the step even with fail-on-findings: 'false'.
        print(f"cannot read input: {e}", file=sys.stderr)
        return 2
    if stream is None or not stream.strip():
        print("no manifests found in the given paths", file=sys.stderr)
        return 2

    present = kinds_in(stream)

    # The individual checks each open a path, and stdin can only be read once, so the
    # merged stream goes to a temp file that every check can re-read.
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tmp:
        tmp.write(stream)
        merged = tmp.name

    results = []
    try:
        for label, items, requires, fn in CHECKS:
            if requires and not (requires & present):
                results.append((label, items, "n/a"))
                print(f"\n--- {label} (catalog {items}): n/a, no {'/'.join(sorted(requires))} in input")
                continue
            print(f"\n--- {label} (catalog {items})")
            results.append((label, items, "PASS" if fn(merged) == 0 else "FAIL"))
    finally:
        os.unlink(merged)

    failed = [r for r in results if r[2] == "FAIL"]
    skipped = [r for r in results if r[2] == "n/a"]

    print("\n" + "=" * 60)
    for label, items, status in results:
        print(f"  {status:>4}  {label} (catalog {items})")
    for label, items, why in NOT_EVALUATED:
        print(f"  {'--':>4}  {label} (catalog {items}): not evaluated, {why}")
    print("=" * 60)
    print(
        f"{len(results) - len(failed) - len(skipped)} passed, {len(failed)} failed, "
        f"{len(skipped)} n/a, {len(NOT_EVALUATED)} check groups not evaluated"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
