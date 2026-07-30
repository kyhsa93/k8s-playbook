#!/usr/bin/env python3
"""Detect namespace/tenancy anti-patterns 14-15 from docs/catalog.md.

Two subcommands:
  namespace  -- flag namespaced resources with no namespace set (defaults to
                "default") or explicitly set to "default"
  rbac       -- flag ClusterRoleBinding usage. A ClusterRole is not itself the
                anti-pattern -- reusing one via a namespace-scoped RoleBinding
                is a legitimate way to avoid duplicating Role definitions.
                ClusterRoleBinding is the actual cluster-wide grant mechanism.
"""
import sys

import yaml

# Resources that are cluster-scoped by definition -- "namespace" doesn't apply to them.
CLUSTER_SCOPED_KINDS = {
    "Namespace", "Node", "PersistentVolume", "StorageClass",
    "ClusterRole", "ClusterRoleBinding", "CustomResourceDefinition",
    "APIService", "PriorityClass", "RuntimeClass",
    "ValidatingWebhookConfiguration", "MutatingWebhookConfiguration",
}


def load_docs(path):
    if path == "-":
        return [d for d in yaml.safe_load_all(sys.stdin) if d]
    with open(path) as f:
        return [d for d in yaml.safe_load_all(f) if d]


def check_namespace(path):
    docs = load_docs(path)
    findings = []
    for doc in docs:
        kind = doc.get("kind")
        if kind in CLUSTER_SCOPED_KINDS:
            continue
        name = doc.get("metadata", {}).get("name", "<unnamed>")
        namespace = doc.get("metadata", {}).get("namespace")
        if namespace is None:
            findings.append(f"{kind}/{name}: no namespace set (defaults to 'default')")
        elif namespace == "default":
            findings.append(f"{kind}/{name}: namespace explicitly set to 'default'")

    if not findings:
        print(f"PASS: {len(docs)} document(s) checked, no workloads in the default namespace")
        return 0
    print(f"FAIL: {len(findings)} resource(s) in the default namespace")
    for f in findings:
        print(f"  {f}")
    return 1


def check_rbac(path):
    docs = load_docs(path)
    findings = []
    for doc in docs:
        if doc.get("kind") != "ClusterRoleBinding":
            continue
        name = doc.get("metadata", {}).get("name", "<unnamed>")
        role_ref = doc.get("roleRef", {}).get("name", "<unknown>")
        findings.append(
            f"ClusterRoleBinding/{name}: grants '{role_ref}' cluster-wide -- "
            f"use a namespace-scoped RoleBinding instead (it can still reference a ClusterRole)"
        )

    if not findings:
        print(f"PASS: {len(docs)} document(s) checked, no cluster-wide RBAC grants found")
        return 0
    print(f"FAIL: {len(findings)} cluster-wide RBAC grant(s) found")
    for f in findings:
        print(f"  {f}")
    return 1


SUBCOMMANDS = {
    "namespace": check_namespace,
    "rbac": check_rbac,
}


def main(argv):
    if len(argv) != 2 or argv[0] not in SUBCOMMANDS:
        print(f"usage: check_namespace_tenancy.py <{'|'.join(SUBCOMMANDS)}> <manifest.yaml|->", file=sys.stderr)
        return 2
    return SUBCOMMANDS[argv[0]](argv[1])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
