#!/usr/bin/env python3
"""Detect workload anti-patterns 1-6 from docs/catalog.md in rendered K8s manifests.

Operates on final rendered YAML (Deployment/StatefulSet/DaemonSet/PodDisruptionBudget),
so it works identically whether the input came from a raw manifest, `kustomize build`,
or `helm template` — no tool-specific assumptions.
"""
import sys

import yaml

WORKLOAD_KINDS = {"Deployment", "StatefulSet", "DaemonSet"}
HA_KINDS = {"Deployment", "StatefulSet"}  # DaemonSet has no replica-count HA concept
MIN_REPLICAS = 2


def check_resources(container):
    resources = container.get("resources", {})
    requests = resources.get("requests", {})
    limits = resources.get("limits", {})
    missing = [k for k in ("cpu", "memory") if k not in requests or k not in limits]
    return [f"resources.requests/limits missing: {', '.join(missing)}"] if missing else []


def check_image_tag(container):
    image = container.get("image", "")
    if ":" not in image:
        return [f"image '{image}' has no tag"]
    tag = image.rsplit(":", 1)[1]
    return [f"image '{image}' uses ':latest' tag"] if tag == "latest" else []


def check_probes(container):
    issues = []
    liveness = container.get("livenessProbe")
    readiness = container.get("readinessProbe")
    if not liveness:
        issues.append("livenessProbe missing")
    if not readiness:
        issues.append("readinessProbe missing")
    if liveness and readiness and liveness == readiness:
        issues.append("livenessProbe and readinessProbe are identical")
    return issues


def check_security_context(pod_spec, container):
    issues = []
    pod_sc = pod_spec.get("securityContext", {})
    container_sc = container.get("securityContext", {})
    run_as_non_root = container_sc.get("runAsNonRoot", pod_sc.get("runAsNonRoot"))
    if run_as_non_root is not True:
        issues.append("runAsNonRoot is not set to true (pod or container level)")
    if container_sc.get("privileged") is True:
        issues.append("container runs with privileged: true")
    return issues


CONTAINER_CHECKS = [
    ("resource-limits", check_resources),
    ("image-tag", check_image_tag),
    ("probes", check_probes),
]


def check_replica_count(doc):
    if doc.get("kind") not in HA_KINDS:
        return []
    replicas = doc.get("spec", {}).get("replicas")
    if replicas is None or replicas < MIN_REPLICAS:
        return [f"replicas={replicas} (expected >= {MIN_REPLICAS} for HA)"]
    return []


def check_anti_affinity(pod_spec):
    if not pod_spec.get("affinity", {}).get("podAntiAffinity"):
        return ["no podAntiAffinity defined; replicas may all land on the same node"]
    return []


def pdb_matches(pdb, workload_labels):
    selector = pdb.get("spec", {}).get("selector", {}).get("matchLabels", {})
    if not selector:
        return False
    return all(workload_labels.get(k) == v for k, v in selector.items())


def check_pdb_coverage(doc, pdbs):
    if doc.get("kind") not in HA_KINDS:
        return []
    workload_labels = doc.get("spec", {}).get("template", {}).get("metadata", {}).get("labels", {})
    if any(pdb_matches(pdb, workload_labels) for pdb in pdbs):
        return []
    return ["no matching PodDisruptionBudget found"]


def check_workload(doc, pdbs):
    findings = []
    pod_spec = doc["spec"]["template"]["spec"]
    kind = doc.get("kind")
    name = doc.get("metadata", {}).get("name", "<unnamed>")
    for container in pod_spec.get("containers", []):
        cname = container.get("name", "<unnamed-container>")
        for label, fn in CONTAINER_CHECKS:
            for issue in fn(container):
                findings.append((kind, name, cname, label, issue))
        for issue in check_security_context(pod_spec, container):
            findings.append((kind, name, cname, "security-context", issue))
    for issue in check_replica_count(doc):
        findings.append((kind, name, "-", "replica-count", issue))
    for issue in check_anti_affinity(pod_spec):
        findings.append((kind, name, "-", "anti-affinity", issue))
    for issue in check_pdb_coverage(doc, pdbs):
        findings.append((kind, name, "-", "pdb-coverage", issue))
    return findings


def main(path):
    if path == "-":
        docs = [d for d in yaml.safe_load_all(sys.stdin) if d]
    else:
        with open(path) as f:
            docs = [d for d in yaml.safe_load_all(f) if d]

    workloads = [d for d in docs if d.get("kind") in WORKLOAD_KINDS]
    pdbs = [d for d in docs if d.get("kind") == "PodDisruptionBudget"]
    if not workloads:
        print(f"no workload manifests (Deployment/StatefulSet/DaemonSet) found in {path}")
        return 1

    findings = [f for doc in workloads for f in check_workload(doc, pdbs)]

    if not findings:
        print(f"PASS: {len(workloads)} workload(s) checked, no anti-patterns found")
        return 0

    print(f"FAIL: {len(findings)} anti-pattern(s) found across {len(workloads)} workload(s)")
    for kind, name, cname, label, issue in findings:
        print(f"  [{label}] {kind}/{name} container={cname}: {issue}")
    return 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: check_workload.py <manifest.yaml|->", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
