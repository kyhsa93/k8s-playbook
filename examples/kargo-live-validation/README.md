# Kargo live-validation example

Minimal, self-contained fixtures used to validate `harness/check_gitops_state.py promotion`
against a **genuinely admitting Kargo controller** -- not just its documented `Stage`
CRD schema. A disposable [kind](https://kind.sigs.k8s.io/) cluster ran cert-manager
(a hard dependency of Kargo's webhook TLS) and a real Kargo install (`oci://ghcr.io/akuity/kargo-charts/kargo`
v1.11.0), then `kargo-resources.yaml` was applied directly -- a `Project`
(`kargo-payment`), a `Warehouse` subscribing to this repo's `main` branch commits,
and the same dev/staging/prod `Stage` pipeline as `fixtures/gitops/promotion/good.yaml`.
The Warehouse genuinely discovered a commit and produced a real `Freight` object; the
resulting live `Stage` objects were dumped with `kubectl get -o yaml` into
`fixtures/gitops/promotion/`.

- `kargo-resources.yaml` -- the `Project`, `Warehouse`, and all three `Stage` objects,
  applied directly to a cluster running the Kargo Helm chart.

To reproduce: install cert-manager, then the Kargo Helm chart
(`oci://ghcr.io/akuity/kargo-charts/kargo`), then
`kubectl apply -f examples/kargo-live-validation/kargo-resources.yaml`.
