#!/usr/bin/env python3
"""Detect secrets-management anti-patterns 9-10 from docs/catalog.md.

Two subcommands:
  exposure   -- scan ConfigMap data and plain container env values for
                secret-like keys that should be sourced from a Secret instead
  plaintext  -- scan manifests for a raw Secret with real data/stringData
                committed directly (should be an encrypted wrapper like
                SealedSecret/ExternalSecret if this is what's checked into Git)
"""
import re
import sys

import yaml

SECRET_KEY_PATTERN = re.compile(
    r"(password|passwd|token|secret|api[_-]?key|apikey|credential|private[_-]?key)",
    re.IGNORECASE,
)

WORKLOAD_KINDS = {"Deployment", "StatefulSet", "DaemonSet"}


def load_docs(path):
    if path == "-":
        return [d for d in yaml.safe_load_all(sys.stdin) if d]
    with open(path) as f:
        return [d for d in yaml.safe_load_all(f) if d]


def check_configmap_exposure(doc):
    if doc.get("kind") != "ConfigMap":
        return []
    name = doc.get("metadata", {}).get("name", "<unnamed>")
    return [
        f"ConfigMap/{name}: key '{key}' looks secret-like but is stored in a ConfigMap"
        for key in doc.get("data", {})
        if SECRET_KEY_PATTERN.search(key)
    ]


def check_plain_env_exposure(doc):
    if doc.get("kind") not in WORKLOAD_KINDS:
        return []
    kind, name = doc["kind"], doc.get("metadata", {}).get("name", "<unnamed>")
    findings = []
    containers = doc.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
    for c in containers:
        cname = c.get("name", "<unnamed>")
        for env in c.get("env", []):
            if "value" in env and SECRET_KEY_PATTERN.search(env.get("name", "")):
                findings.append(
                    f"{kind}/{name} container={cname}: env '{env['name']}' is a plain value, "
                    f"not sourced from a Secret (secretKeyRef/envFrom)"
                )
    return findings


def check_exposure(path):
    docs = load_docs(path)
    findings = [
        f for doc in docs
        for f in check_configmap_exposure(doc) + check_plain_env_exposure(doc)
    ]

    if not findings:
        print(f"PASS: {len(docs)} document(s) checked, no plaintext secret exposure found")
        return 0
    print(f"FAIL: {len(findings)} secret-exposure finding(s)")
    for f in findings:
        print(f"  {f}")
    return 1


def check_plaintext(path):
    docs = load_docs(path)
    findings = []
    for doc in docs:
        if doc.get("kind") != "Secret":
            continue
        name = doc.get("metadata", {}).get("name", "<unnamed>")
        if doc.get("data") or doc.get("stringData"):
            findings.append(f"Secret/{name}: plaintext data/stringData committed directly "
                             f"(use a SealedSecret/ExternalSecret wrapper instead)")

    if not findings:
        print(f"PASS: {len(docs)} document(s) checked, no plaintext Secret manifests found")
        return 0
    print(f"FAIL: {len(findings)} plaintext Secret(s) found")
    for f in findings:
        print(f"  {f}")
    return 1


SUBCOMMANDS = {
    "exposure": check_exposure,
    "plaintext": check_plaintext,
}


def main(argv):
    if len(argv) != 2 or argv[0] not in SUBCOMMANDS:
        print(f"usage: check_secrets.py <{'|'.join(SUBCOMMANDS)}> <manifest.yaml|->", file=sys.stderr)
        return 2
    return SUBCOMMANDS[argv[0]](argv[1])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
