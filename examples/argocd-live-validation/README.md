# Argo CD live-validation example

Minimal, self-contained fixtures used to validate `harness/check_gitops_state.py apps` against a
**genuinely reconciling Argo CD controller** — not just documentation. A disposable [kind](https://kind.sigs.k8s.io/)
cluster ran a real Argo CD install pointed at this directory (via `repoURL: https://github.com/kyhsa93/k8s-playbook.git`),
and the resulting live Application objects were dumped with `kubectl get -o yaml` into
`fixtures/gitops/apps/` — same pattern as the earlier `kind` cluster round for drift detection.

- `apps/` — child `Application` manifests for the classic App-of-Apps pattern (`directory.recurse: true`
  from a root Application pointed at this path)
- `workloads/` — trivial target Deployments the child Applications sync (content doesn't matter, only
  used to give Argo CD something real to reconcile)
- `applicationset.yaml` — a real `ApplicationSet` (list generator) pointed at the same two workloads,
  to validate the ownerReferences signal separately from the directory-recursion signal

To reproduce: apply a root `Application` with `source.path: examples/argocd-live-validation/apps` and
`source.directory.recurse: true` against this repo, or apply `applicationset.yaml` directly.
