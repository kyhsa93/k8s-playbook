#!/usr/bin/env python3
"""Detect configuration-management anti-patterns 7-8 from docs/catalog.md.

Two subcommands:
  env-parity    -- diff N environment renders, flag env-sensitive fields that
                    never actually vary across environments (evidence they're
                    hardcoded in the base instead of overlaid per environment)
  values-bloat  -- compare a Helm values.yaml's parameter surface against how
                    many of those keys are ever overridden across per-env
                    values files ("god values file" detection)
"""
import re
import sys

import yaml

ENV_SENSITIVE_NAME = re.compile(r"(HOST|DOMAIN|URL|ENVIRONMENT|REGION|STAGE)", re.IGNORECASE)
WORKLOAD_KINDS = {"Deployment", "StatefulSet", "DaemonSet"}


def load_docs(path):
    with open(path) as f:
        return [d for d in yaml.safe_load_all(f) if d]


def ingress_hosts(docs):
    hosts = {}
    for d in docs:
        if d.get("kind") != "Ingress":
            continue
        name = d.get("metadata", {}).get("name", "<unnamed>")
        rules = d.get("spec", {}).get("rules", [])
        hosts[name] = tuple(r.get("host") for r in rules)
    return hosts


def env_sensitive_vars(docs):
    values = {}
    for d in docs:
        if d.get("kind") not in WORKLOAD_KINDS:
            continue
        containers = d.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
        for c in containers:
            cname = c.get("name", "<unnamed>")
            for env in c.get("env", []):
                if "value" not in env:
                    continue
                name = env.get("name", "")
                if ENV_SENSITIVE_NAME.search(name):
                    values[(cname, name)] = env["value"]
    return values


def check_env_parity(env_paths):
    envs = {path: load_docs(path) for path in env_paths}

    findings = []
    per_env_hosts = {path: ingress_hosts(docs) for path, docs in envs.items()}
    all_ingress_names = set().union(*(set(h) for h in per_env_hosts.values()))
    for name in sorted(all_ingress_names):
        values = {per_env_hosts[path].get(name) for path in envs}
        if len(values) == 1:
            findings.append(f"Ingress/{name}: host {next(iter(values))!r} identical across all {len(envs)} environments")

    per_env_vars = {path: env_sensitive_vars(docs) for path, docs in envs.items()}
    all_keys = set().union(*(set(v) for v in per_env_vars.values()))
    for cname, name in sorted(all_keys):
        values = {per_env_vars[path].get((cname, name)) for path in envs}
        if len(values) == 1:
            findings.append(f"container={cname} env={name}: value {next(iter(values))!r} identical across all {len(envs)} environments")

    if not findings:
        print(f"PASS: {len(envs)} environment(s) compared, environment-sensitive fields all vary as expected")
        return 0
    print(f"FAIL: {len(findings)} field(s) look environment-specific but never vary -- likely hardcoded in the base")
    for f in findings:
        print(f"  {f}")
    return 1


def flatten_leaf_keys(node, prefix=""):
    if isinstance(node, dict) and node:
        keys = set()
        for k, v in node.items():
            keys |= flatten_leaf_keys(v, f"{prefix}.{k}" if prefix else k)
        return keys
    if isinstance(node, list) and node:
        keys = set()
        for i, v in enumerate(node):
            keys |= flatten_leaf_keys(v, f"{prefix}[{i}]")
        return keys
    return {prefix}


OVERRIDE_RATIO_THRESHOLD = 0.3
MIN_KEYS_FOR_BLOAT_CHECK = 8


def check_values_bloat(values_path, override_paths):
    with open(values_path) as f:
        base = yaml.safe_load(f) or {}
    base_keys = flatten_leaf_keys(base)

    overridden = set()
    for path in override_paths:
        with open(path) as f:
            override = yaml.safe_load(f) or {}
        overridden |= flatten_leaf_keys(override)

    touched = overridden & base_keys
    ratio = len(touched) / len(base_keys) if base_keys else 0
    print(f"{values_path}: {len(base_keys)} parameterized key(s), {len(touched)} ever overridden "
          f"across {len(override_paths)} env file(s) (ratio={ratio:.0%})")

    if ratio < OVERRIDE_RATIO_THRESHOLD and len(base_keys) >= MIN_KEYS_FOR_BLOAT_CHECK:
        print(f"FAIL: override ratio {ratio:.0%} is below the {OVERRIDE_RATIO_THRESHOLD:.0%} threshold on a "
              f"{len(base_keys)}-key values.yaml -- looks like a 'god values file', most fields are never "
              f"actually varied per environment")
        return 1
    print("PASS: values.yaml parameterization roughly matches actual per-environment usage")
    return 0


def main(argv):
    if len(argv) < 3 or argv[0] not in ("env-parity", "values-bloat"):
        print("usage:\n"
              "  check_config_mgmt.py env-parity <env1.yaml> <env2.yaml> [envN.yaml ...]\n"
              "  check_config_mgmt.py values-bloat <values.yaml> <override1.yaml> [overrideN.yaml ...]",
              file=sys.stderr)
        return 2
    if argv[0] == "env-parity":
        return check_env_parity(argv[1:])
    return check_values_bloat(argv[1], argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
