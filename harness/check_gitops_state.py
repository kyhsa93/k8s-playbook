#!/usr/bin/env python3
"""Detect GitOps-state anti-patterns 11-13 from docs/catalog.md.

Three subcommands, one per catalog item:
  drift      -- diff declared (Git) state vs live cluster state, flag any mismatch
  promotion  -- check that every non-entry Stage has a verification gate
  apps       -- check that Applications/Kustomizations are managed as a group
                (App-of-Apps / Kustomization tree), not registered one by one
"""
import sys

import yaml

IGNORED_METADATA_KEYS = {
    "resourceVersion", "uid", "generation", "creationTimestamp",
    "managedFields", "selfLink",
}


def load_docs(path):
    with open(path) as f:
        return [d for d in yaml.safe_load_all(f) if d]


def resource_key(doc):
    md = doc.get("metadata", {})
    return (doc.get("kind"), md.get("namespace", "default"), md.get("name"))


def diff_paths(a, b, prefix):
    """Recursively collect dotted-path differences between two values."""
    if isinstance(a, dict) and isinstance(b, dict):
        diffs = []
        for k in sorted(set(a) | set(b)):
            path = f"{prefix}.{k}"
            if k not in a:
                diffs.append(f"{path}: missing in declared, present in live ({b[k]!r})")
            elif k not in b:
                diffs.append(f"{path}: present in declared ({a[k]!r}), missing in live")
            else:
                diffs.extend(diff_paths(a[k], b[k], path))
        return diffs
    if a != b:
        return [f"{prefix}: declared={a!r} live={b!r}"]
    return []


def check_drift(declared_path, live_path):
    declared = {resource_key(d): d for d in load_docs(declared_path)}
    live = {resource_key(d): d for d in load_docs(live_path)}

    findings = []
    for key in sorted(set(declared) | set(live), key=lambda k: (k[0] or "", k[1] or "", k[2] or "")):
        kind, ns, name = key
        label = f"{kind}/{name} (ns={ns})"
        if key not in live:
            findings.append(f"{label}: declared in Git but not found on the cluster")
            continue
        if key not in declared:
            findings.append(f"{label}: exists on the cluster but not declared in Git (manually created)")
            continue
        d_doc, l_doc = declared[key], live[key]
        for section in ("spec", "data"):
            findings.extend(
                f"{label}: {diff}"
                for diff in diff_paths(d_doc.get(section, {}), l_doc.get(section, {}), section)
            )

    if not findings:
        print(f"PASS: {len(declared)} resource(s) checked, live state matches Git exactly")
        return 0
    print(f"FAIL: {len(findings)} drift finding(s) between Git and live cluster state")
    for f in findings:
        print(f"  {f}")
    return 1


def check_promotion(path):
    stages = [d for d in load_docs(path) if d.get("kind") == "Stage"]
    if not stages:
        print(f"no Stage resources found in {path}")
        return 1

    # A stage with no incoming freight source is a pipeline entry point (e.g. "dev")
    # and needs no verification gate of its own; every downstream stage does.
    findings = []
    for stage in stages:
        name = stage.get("metadata", {}).get("name", "<unnamed>")
        freight = stage.get("spec", {}).get("requestedFreight", [])
        has_upstream = any(f.get("sources", {}).get("stages") for f in freight)
        if not has_upstream:
            continue
        verification = stage.get("spec", {}).get("verification", {})
        checks = verification.get("analysisTemplates") or verification.get("checks")
        if not checks:
            findings.append(f"Stage/{name}: no verification gate before promotion")

    if not findings:
        print(f"PASS: {len(stages)} stage(s) checked, every promotion has a verification gate")
        return 0
    print(f"FAIL: {len(findings)} stage(s) missing a verification gate")
    for f in findings:
        print(f"  {f}")
    return 1


APP_KINDS = {"Application", "Kustomization"}


def check_apps(path):
    apps = [d for d in load_docs(path) if d.get("kind") in APP_KINDS]
    if not apps:
        print(f"no Application/Kustomization resources found in {path}")
        return 1
    if len(apps) == 1:
        print("PASS: only 1 app resource, no app-of-apps structure needed")
        return 0

    names = {a.get("metadata", {}).get("name") for a in apps}
    has_root_managed_child = any(
        any(ref.get("name") in names for ref in a.get("metadata", {}).get("ownerReferences", []))
        for a in apps
    )

    if has_root_managed_child:
        print(f"PASS: {len(apps)} app(s) checked, managed via an App-of-Apps/Kustomization tree")
        return 0
    print(f"FAIL: {len(apps)} apps found, none has an ownerReference to a root app "
          f"-- looks like they were registered one by one by hand")
    return 1


SUBCOMMANDS = {
    "drift": (check_drift, ["declared.yaml", "live.yaml"]),
    "promotion": (check_promotion, ["stages.yaml"]),
    "apps": (check_apps, ["apps.yaml"]),
}


def usage():
    lines = [f"  check_gitops_state.py {name} {' '.join(f'<{a}>' for a in args)}"
             for name, (_, args) in SUBCOMMANDS.items()]
    return "usage:\n" + "\n".join(lines)


def main(argv):
    if not argv or argv[0] not in SUBCOMMANDS:
        print(usage(), file=sys.stderr)
        return 2
    fn, args = SUBCOMMANDS[argv[0]]
    if len(argv) - 1 != len(args):
        print(usage(), file=sys.stderr)
        return 2
    return fn(*argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
