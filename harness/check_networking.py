#!/usr/bin/env python3
"""Detect networking anti-patterns 16-17 from docs/catalog.md.

Two subcommands:
  netpol -- flag namespaces with Deployment/StatefulSet/DaemonSet/Service
            resources but no NetworkPolicy at all (implicit allow-all traffic)
  tls    -- flag Ingress resources with no spec.tls (plaintext HTTP)
"""
import sys

import yaml

WORKLOAD_KINDS = {"Deployment", "StatefulSet", "DaemonSet", "Service"}


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


def check_netpol(path):
    docs = load_docs(path)
    namespaces_with_workloads = set()
    namespaces_with_netpol = set()
    for doc in docs:
        kind = doc.get("kind")
        namespace = doc.get("metadata", {}).get("namespace", "default")
        if kind in WORKLOAD_KINDS:
            namespaces_with_workloads.add(namespace)
        elif kind == "NetworkPolicy":
            namespaces_with_netpol.add(namespace)

    exposed = sorted(namespaces_with_workloads - namespaces_with_netpol)
    if not exposed:
        print(f"PASS: {len(docs)} document(s) checked, every namespace with workloads has a NetworkPolicy")
        return 0
    print(f"FAIL: {len(exposed)} namespace(s) with workloads but no NetworkPolicy (implicit allow-all)")
    for ns in exposed:
        print(f"  namespace/{ns}: no NetworkPolicy found")
    return 1


def check_tls(path):
    docs = load_docs(path)
    ingresses = [d for d in docs if d.get("kind") == "Ingress"]
    if not ingresses:
        print(f"no Ingress resources found in {path}")
        return 1

    findings = []
    for doc in ingresses:
        name = doc.get("metadata", {}).get("name", "<unnamed>")
        if not doc.get("spec", {}).get("tls"):
            findings.append(f"Ingress/{name}: no spec.tls -- served over plaintext HTTP")

    if not findings:
        print(f"PASS: {len(ingresses)} Ingress resource(s) checked, all have tls configured")
        return 0
    print(f"FAIL: {len(findings)} Ingress resource(s) with no TLS")
    for f in findings:
        print(f"  {f}")
    return 1


SUBCOMMANDS = {
    "netpol": check_netpol,
    "tls": check_tls,
}


def main(argv):
    if len(argv) != 2 or argv[0] not in SUBCOMMANDS:
        print(f"usage: check_networking.py <{'|'.join(SUBCOMMANDS)}> <manifest.yaml|->", file=sys.stderr)
        return 2
    return SUBCOMMANDS[argv[0]](argv[1])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
