# k8s-playbook

The goal of this repo is to **define recurring Kubernetes deployment anti-patterns and catch them automatically**.

## Principle

The core deliverable here is an **anti-pattern catalog + a detection harness**. Comparing tools (raw manifest vs Kustomize vs Helm, or Argo CD vs Flux) is not the point — that variety only exists as a fixture to prove the harness detects real, general violations rather than something that happens to match one tool's output shape.

- Define the [anti-pattern catalog](docs/catalog.md) first, pairing each anti-pattern with its correct-pattern counterpart.
- Build and validate the harness against a minimal fixture (a single raw manifest) first.
- Only then add Kustomize/Helm, Argo CD/Flux, etc. as fixtures to confirm the harness generalizes across tools.

## Status

- [x] Anti-pattern ↔ correct-pattern catalog draft ([docs/catalog.md](docs/catalog.md))
- [x] Minimal fixture (raw manifest) + post-render workload harness (`harness/check_workload.py`, catalog items 1-6: resources, image tag, probes, security context, replica count, anti-affinity, PDB coverage)
- [x] Kustomize + Helm fixtures added, harness genericity validated for items 1-6 (`scripts/verify-genericity.sh`)
- [ ] GitOps-state harness (drift, promotion gates)
- [ ] Add Argo CD/Flux fixtures, validate harness genericity

## Usage

```bash
# check a raw manifest directly
python3 harness/check_workload.py fixtures/raw/bad-deployment.yaml   # exits 1, lists findings
python3 harness/check_workload.py fixtures/raw/good-deployment.yaml  # exits 0

# check rendered Kustomize/Helm output via stdin
kustomize build fixtures/kustomize/good | python3 harness/check_workload.py -
helm template fixtures/helm/payment-api -f fixtures/helm/payment-api/values-good.yaml | python3 harness/check_workload.py -

# run all raw/Kustomize/Helm fixtures through the harness and assert the expected verdict
scripts/verify-genericity.sh
```

Requires `kustomize` and `helm` on `PATH` to run the Kustomize/Helm fixtures and `scripts/verify-genericity.sh`.
