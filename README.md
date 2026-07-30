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
- [x] GitOps-state harness (`harness/check_gitops_state.py`, catalog items 11-13: drift, promotion gates, App-of-Apps/Kustomization-tree structure)
- [x] Genericity validated against real Argo CD/Flux/Kargo schemas and a real cluster (`scripts/verify-gitops-state.sh`) — this pass found and fixed 2 real bugs (see below)

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

# GitOps-state checks (catalog items 11-13), one subcommand per item
python3 harness/check_gitops_state.py drift fixtures/gitops/drift/declared.yaml fixtures/gitops/drift/live-good.yaml   # exits 0
python3 harness/check_gitops_state.py drift fixtures/gitops/drift/declared.yaml fixtures/gitops/drift/live-bad.yaml    # exits 1
python3 harness/check_gitops_state.py promotion fixtures/gitops/promotion/good.yaml               # exits 0 (real Kargo Stage schema)
python3 harness/check_gitops_state.py promotion fixtures/gitops/promotion/bad.yaml                # exits 1
python3 harness/check_gitops_state.py apps fixtures/gitops/apps/good-argocd-recurse.yaml          # exits 0 (Argo CD App-of-Apps)
python3 harness/check_gitops_state.py apps fixtures/gitops/apps/good-flux-dependson.yaml          # exits 0 (Flux Kustomization tree)
python3 harness/check_gitops_state.py apps fixtures/gitops/apps/good-applicationset.yaml          # exits 0 (Argo CD ApplicationSet)
python3 harness/check_gitops_state.py apps fixtures/gitops/apps/bad.yaml                          # exits 1

# run all GitOps-state fixtures through the harness and assert the expected verdict
scripts/verify-gitops-state.sh
```

Requires `kustomize` and `helm` on `PATH` to run the Kustomize/Helm fixtures and `scripts/verify-genericity.sh`.

### GitOps-state genericity validation

Unlike the workload harness (validated by piping real `kustomize`/`helm` renders through it), Argo CD/Flux/Kargo
are cluster controllers with no standalone "render" equivalent, so each check was validated against the closest
real-tool ground truth available:

- **drift** was validated against a real cluster: a disposable [kind](https://kind.sigs.k8s.io/) cluster had
  `declared.yaml` applied, then the live state was dumped with genuine `kubectl get -o yaml` (`live-good.yaml`),
  and again after simulating manual out-of-band changes with `kubectl scale`/`set image`/`patch`/`create secret`
  (`live-bad.yaml`). This is real captured output, not hand-written YAML. It caught a real bug: the API server
  and admission defaulting fill in fields like `spec.strategy`, `imagePullPolicy`, `resources`, `dnsPolicy`,
  `securityContext`, etc. even when Git never declared them, which flooded every untouched resource with
  false-positive drift. Fixed with an explicit `SERVER_DEFAULTED_KEYS` allowlist in `check_drift`, plus
  name-matched list diffing so per-container defaulting doesn't fail the whole `containers` list.
- **apps** was validated against documented real Argo CD/Flux behavior (fixtures in `good-argocd-recurse.yaml`,
  `good-flux-dependson.yaml`, `good-applicationset.yaml`). This caught a bigger bug: the original check assumed
  child apps carry an `ownerReference` to a root `Application`, but that pattern doesn't exist in either tool —
  classic Argo CD App-of-Apps uses `spec.source.directory.recurse: true` (no ownerReferences; deleting the root
  without a finalizer famously orphans the children), Flux expresses the tree via `spec.dependsOn` (the
  kustomize-controller never stamps ownerReferences on a Kustomization it didn't generate), and ownerReferences
  are only real for Argo CD `ApplicationSet`-generated apps, pointing at the `ApplicationSet`, not a root
  `Application`. `check_apps` now recognizes all three real signals instead of one invented one.
- **promotion** fixtures were rewritten against Kargo's real `Stage` CRD schema (`kargo.akuity.io/v1alpha1`,
  `spec.requestedFreight[].origin.{kind,name}`, `spec.verification.analysisTemplates`) — the check's logic
  (`sources.stages` + `verification.analysisTemplates`) already matched real Kargo, so no logic change was needed.
