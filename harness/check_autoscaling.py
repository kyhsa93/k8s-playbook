#!/usr/bin/env python3
"""Detect autoscaling anti-patterns 18-19 from docs/catalog.md.

Two subcommands:
  requests -- flag HPAs whose scaleTargetRef workload has container(s) with no
              resources.requests (HPA can't compute utilization %, so it's
              silently broken)
  minmax   -- flag HPAs where minReplicas == maxReplicas (no actual scaling
              range, just overhead)
"""
import sys

import yaml

WORKLOAD_KINDS = {"Deployment", "StatefulSet", "DaemonSet"}


def _expand_lists(docs):
    # `kubectl get <kind> <name1> <name2> -o yaml` wraps results in a single
    # `kind: List` document with an `items:` array instead of `---`-separated
    # docs -- expand it so every check below sees the individual resources.
    expanded = []
    for d in docs:
        if d.get("kind") == "List":
            expanded.extend(item for item in d.get("items", []) if item)
        else:
            expanded.append(d)
    return expanded


def load_docs(path):
    if path == "-":
        return _expand_lists(d for d in yaml.safe_load_all(sys.stdin) if d)
    with open(path) as f:
        return _expand_lists(d for d in yaml.safe_load_all(f) if d)


def _workload_key(doc):
    return (
        doc.get("kind"),
        doc.get("metadata", {}).get("namespace", "default"),
        doc.get("metadata", {}).get("name"),
    )


def check_requests(path):
    docs = load_docs(path)
    workloads = {_workload_key(d): d for d in docs if d.get("kind") in WORKLOAD_KINDS}
    hpas = [d for d in docs if d.get("kind") == "HorizontalPodAutoscaler"]

    if not hpas:
        print(f"no HorizontalPodAutoscaler resources found in {path}")
        return 1

    findings = []
    for hpa in hpas:
        name = hpa.get("metadata", {}).get("name", "<unnamed>")
        namespace = hpa.get("metadata", {}).get("namespace", "default")
        ref = hpa.get("spec", {}).get("scaleTargetRef", {})
        target = workloads.get((ref.get("kind"), namespace, ref.get("name")))
        if target is None:
            findings.append(f"HPA/{name}: scaleTargetRef {ref.get('kind')}/{ref.get('name')} not found in input")
            continue
        containers = target.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
        missing = [c.get("name", "<unnamed>") for c in containers if not c.get("resources", {}).get("requests")]
        if missing:
            findings.append(
                f"HPA/{name}: target {ref.get('kind')}/{ref.get('name')} has container(s) {missing} "
                f"with no resources.requests -- HPA can't compute utilization %"
            )

    if not findings:
        print(f"PASS: {len(hpas)} HPA(s) checked, all targets have resource requests")
        return 0
    print(f"FAIL: {len(findings)} HPA(s) targeting workloads without resource requests")
    for f in findings:
        print(f"  {f}")
    return 1


def check_minmax(path):
    docs = load_docs(path)
    hpas = [d for d in docs if d.get("kind") == "HorizontalPodAutoscaler"]

    if not hpas:
        print(f"no HorizontalPodAutoscaler resources found in {path}")
        return 1

    findings = []
    for hpa in hpas:
        name = hpa.get("metadata", {}).get("name", "<unnamed>")
        spec = hpa.get("spec", {})
        min_r, max_r = spec.get("minReplicas"), spec.get("maxReplicas")
        if min_r is not None and min_r == max_r:
            findings.append(f"HPA/{name}: minReplicas == maxReplicas == {min_r} -- no actual scaling range")

    if not findings:
        print(f"PASS: {len(hpas)} HPA(s) checked, all have a real min/max scaling range")
        return 0
    print(f"FAIL: {len(findings)} HPA(s) with minReplicas == maxReplicas")
    for f in findings:
        print(f"  {f}")
    return 1


SUBCOMMANDS = {
    "requests": check_requests,
    "minmax": check_minmax,
}


def main(argv):
    if len(argv) != 2 or argv[0] not in SUBCOMMANDS:
        print(f"usage: check_autoscaling.py <{'|'.join(SUBCOMMANDS)}> <manifest.yaml|->", file=sys.stderr)
        return 2
    return SUBCOMMANDS[argv[0]](argv[1])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
