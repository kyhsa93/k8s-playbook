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

# Fields the Kubernetes API server / admission defaulting fills in on live Deployment-family
# resources even when Git never declared them -- confirmed by applying declared.yaml to a
# real kind cluster and diffing the live dump (see fixtures/gitops/drift/live-good.yaml).
# Without this list every untouched resource would flood the report with false-positive
# "drift" for fields nobody ever touched.
SERVER_DEFAULTED_KEYS = {
    "progressDeadlineSeconds", "revisionHistoryLimit", "strategy",
    "dnsPolicy", "restartPolicy", "schedulerName", "terminationGracePeriodSeconds",
    "securityContext", "imagePullPolicy", "resources",
    "terminationMessagePath", "terminationMessagePolicy", "creationTimestamp",
}


def load_docs(path):
    with open(path) as f:
        return [d for d in yaml.safe_load_all(f) if d]


def resource_key(doc):
    md = doc.get("metadata", {})
    return (doc.get("kind"), md.get("namespace", "default"), md.get("name"))


def diff_paths(a, b, prefix):
    """Recursively collect dotted-path differences between two values.

    Dicts: a key present only in `b` (live) is real drift UNLESS it's a known
    server-defaulted field. Lists of named objects (containers, volumes, ...) are
    matched by name so per-item server defaulting doesn't produce a whole-list mismatch.
    """
    if isinstance(a, dict) and isinstance(b, dict):
        diffs = []
        for k in sorted(set(a) | set(b)):
            path = f"{prefix}.{k}"
            if k not in a:
                if k in SERVER_DEFAULTED_KEYS:
                    continue
                diffs.append(f"{path}: missing in declared, present in live ({b[k]!r})")
            elif k not in b:
                diffs.append(f"{path}: present in declared ({a[k]!r}), missing in live")
            else:
                diffs.extend(diff_paths(a[k], b[k], path))
        return diffs
    if isinstance(a, list) and isinstance(b, list) and a and all(isinstance(x, dict) and "name" in x for x in a):
        b_by_name = {x.get("name"): x for x in b if isinstance(x, dict)}
        diffs = []
        for item in a:
            name = item["name"]
            path = f"{prefix}[name={name}]"
            if name not in b_by_name:
                diffs.append(f"{path}: present in declared, missing in live")
            else:
                diffs.extend(diff_paths(item, b_by_name[name], path))
        for name in set(b_by_name) - {item["name"] for item in a}:
            diffs.append(f"{prefix}[name={name}]: not declared in Git, present in live")
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


def has_flux_dependency_tree(apps, names):
    # Flux expresses parent/child ordering via spec.dependsOn -- the controller never
    # stamps ownerReferences on a Kustomization it didn't itself generate.
    return any(
        any(dep.get("name") in names for dep in a.get("spec", {}).get("dependsOn", []))
        for a in apps
    )


def has_argocd_directory_recursion(apps):
    # Classic Argo CD App-of-Apps: a root Application syncs a directory containing the
    # other Application manifests via spec.source(s).directory.recurse: true. Deleting
    # the root leaves children orphaned (no ownerReferences involved).
    for a in apps:
        if a.get("kind") != "Application":
            continue
        sources = a.get("spec", {}).get("sources") or [a.get("spec", {}).get("source", {})]
        if any(s.get("directory", {}).get("recurse") for s in sources):
            return True
    return False


def has_applicationset_ownership(docs):
    # ApplicationSet is the one real pattern where ownerReferences actually get set --
    # by the ApplicationSet controller, pointing at the ApplicationSet, not a root Application.
    appset_names = {d.get("metadata", {}).get("name") for d in docs if d.get("kind") == "ApplicationSet"}
    if not appset_names:
        return False
    return any(
        d.get("kind") == "Application"
        and any(
            ref.get("kind") == "ApplicationSet" and ref.get("name") in appset_names
            for ref in d.get("metadata", {}).get("ownerReferences", [])
        )
        for d in docs
    )


def check_apps(path):
    docs = load_docs(path)
    apps = [d for d in docs if d.get("kind") in APP_KINDS]
    if not apps:
        print(f"no Application/Kustomization resources found in {path}")
        return 1
    if len(apps) == 1:
        print("PASS: only 1 app resource, no app-of-apps structure needed")
        return 0

    names = {a.get("metadata", {}).get("name") for a in apps}
    if (
        has_flux_dependency_tree(apps, names)
        or has_argocd_directory_recursion(apps)
        or has_applicationset_ownership(docs)
    ):
        print(f"PASS: {len(apps)} app(s) checked, managed via an App-of-Apps/Kustomization tree")
        return 0
    print(f"FAIL: {len(apps)} apps found, no dependsOn tree, directory-recursion root, or "
          f"ApplicationSet ownership found -- looks like they were registered one by one by hand")
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
