# Flux live-validation example

Minimal, self-contained fixtures used to validate `harness/check_gitops_state.py apps`'s
`has_flux_dependency_tree` signal against a **genuinely reconciling Flux controller** --
not just the `kustomize.toolkit.fluxcd.io/v1` CRD schema. A disposable [kind](https://kind.sigs.k8s.io/)
cluster ran a real `flux install` (the core controllers only, no `flux bootstrap`), then
`flux-kustomizations.yaml` was applied directly -- a `GitRepository` pointed at this repo's
`main` branch, plus a root `infra` Kustomization and two dependents (`payment-api`,
`order-api`) that declare a real `spec.dependsOn: [{name: infra}]`. The resulting live
`Kustomization` objects were dumped with `kubectl get -o yaml` into `fixtures/gitops/apps/`
-- same pattern as the earlier `kind` cluster rounds for drift detection and Argo CD.

- `workloads/infra/` -- a trivial ConfigMap the root Kustomization reconciles.
- `workloads/payment-api/`, `workloads/order-api/` -- trivial target Deployments the two
  dependent Kustomizations reconcile (content doesn't matter, only used to give
  kustomize-controller something real to apply).
- `flux-kustomizations.yaml` -- the `GitRepository` source and all three `Kustomization`
  objects, applied directly to a cluster running `flux install`.

To reproduce: `flux install`, then `kubectl apply -f examples/flux-live-validation/flux-kustomizations.yaml`
against this repo's `main` branch.
