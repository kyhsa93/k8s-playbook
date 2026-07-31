# k8s-playbook

![verify](https://github.com/kyhsa93/k8s-playbook/actions/workflows/verify.yml/badge.svg)

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
- [x] Config-management harness (`harness/check_config_mgmt.py`, catalog items 7-8: env-parity, values-file bloat) and Secrets harness (`harness/check_secrets.py`, catalog items 9-10: exposure, plaintext-in-Git), built against minimal fixtures (`scripts/verify-config-secrets.sh`)
- [x] Namespace/Tenancy harness (`harness/check_namespace_tenancy.py`, catalog items 14-15: default-namespace usage, ClusterRoleBinding vs. namespace-scoped RoleBinding), built against minimal fixtures (`scripts/verify-namespace-tenancy.sh`) — all 15 catalog items now have a first-pass implementation
- [x] Config-management genericity validated (`scripts/verify-config-mgmt-genericity.sh`, closes issue #1) against a real Kustomize base+overlays, a real Helm chart, and a real public chart's values.yaml — no bugs found in the check logic itself, but it surfaced a real limitation (see below)
- [x] Secrets genericity validated (`scripts/verify-secrets-genericity.sh`, closes issue #2) against real Kustomize/Helm renders and real SealedSecret/ExternalSecret schemas — no bugs found
- [x] Namespace/Tenancy genericity validated (`scripts/verify-namespace-tenancy-genericity.sh`, closes issue #3) against real Kustomize/Helm namespace assignment and the real ingress-nginx chart's conditional RBAC scope templating — no bugs found. **All 15 catalog items are now both implemented and genericity-validated against real tooling.**
- [x] `scripts/verify-all.sh` runs every verification script with one command, wired into CI (`.github/workflows/verify.yml`) on every push/PR to `main`
- [x] `apps` (item 13) validated against a genuinely reconciling Argo CD controller — not just schemas/docs (`scripts/verify-live-argocd.sh`) — found and fixed a real bug affecting all 5 harnesses, and documented a real usage caveat (see below)

## Setup

```bash
pip install -r requirements.txt   # PyYAML, needed by every harness/*.py script
```

`kustomize` and `helm` are also required for the Kustomize/Helm-backed checks (everything except the minimal
raw-manifest fixtures). Install them onto `PATH` yourself, or place them under `.tools/bin/` (gitignored) the
way CI does — see `.github/workflows/verify.yml` for the exact versions this repo is validated against
(kustomize v5.8.1, Helm v4.2.3).

## Usage

```bash
# run every verification script in one command (what CI runs)
scripts/verify-all.sh

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

# Configuration-management checks (catalog items 7-8)
python3 harness/check_config_mgmt.py env-parity fixtures/config-mgmt/env-parity/bad/{dev,staging,prod}.yaml    # exits 1
python3 harness/check_config_mgmt.py env-parity fixtures/config-mgmt/env-parity/good/{dev,staging,prod}.yaml   # exits 0
python3 harness/check_config_mgmt.py values-bloat fixtures/config-mgmt/values-bloat/bad/values.yaml \
  fixtures/config-mgmt/values-bloat/bad/values-{dev,staging,prod}.yaml    # exits 1, "god values file"
python3 harness/check_config_mgmt.py values-bloat fixtures/config-mgmt/values-bloat/good/values.yaml \
  fixtures/config-mgmt/values-bloat/good/values-{dev,staging,prod}.yaml   # exits 0

# Secrets checks (catalog items 9-10)
python3 harness/check_secrets.py exposure fixtures/secrets/exposure-bad.yaml    # exits 1
python3 harness/check_secrets.py exposure fixtures/secrets/exposure-good.yaml   # exits 0
python3 harness/check_secrets.py plaintext fixtures/secrets/plaintext-bad.yaml  # exits 1
python3 harness/check_secrets.py plaintext fixtures/secrets/plaintext-good.yaml # exits 0

# run all config-mgmt/secrets fixtures through their harnesses and assert the expected verdict
scripts/verify-config-secrets.sh

# Namespace/Tenancy checks (catalog items 14-15)
python3 harness/check_namespace_tenancy.py namespace fixtures/namespace-tenancy/namespace-bad.yaml   # exits 1
python3 harness/check_namespace_tenancy.py namespace fixtures/namespace-tenancy/namespace-good.yaml  # exits 0
python3 harness/check_namespace_tenancy.py rbac fixtures/namespace-tenancy/rbac-bad.yaml   # exits 1, ClusterRoleBinding
python3 harness/check_namespace_tenancy.py rbac fixtures/namespace-tenancy/rbac-good.yaml  # exits 0, namespaced RoleBinding

# run all namespace/tenancy fixtures through the harness and assert the expected verdict
scripts/verify-namespace-tenancy.sh

# Config-management genericity: real kustomize/helm renders + a real public chart (closes issue #1)
scripts/verify-config-mgmt-genericity.sh

# Secrets genericity: real kustomize/helm renders + real SealedSecret/ExternalSecret schemas (closes issue #2)
scripts/verify-secrets-genericity.sh

# Namespace/Tenancy genericity: real kustomize/helm namespace assignment + a real chart's RBAC scope toggle (closes issue #3)
scripts/verify-namespace-tenancy-genericity.sh

# apps (item 13) against a genuinely reconciling Argo CD controller, not just schemas/docs
scripts/verify-live-argocd.sh
```

See [Setup](#setup) above for `kustomize`/`helm`/PyYAML requirements.

### Live Argo CD genericity validation for `apps` (item 13)

Every other GitOps-state check was validated against real schemas/docs or a real cluster's API server, but
`apps` had only ever been checked against documentation of how Argo CD/Flux/ApplicationSet behave — never a
genuinely reconciling controller. This round closed that gap, scoped to Argo CD only (Flux/Kargo live-controller
testing is a heavier lift, left for later if picked up).

**Setup:** a disposable kind cluster ran a real Argo CD install (`argoproj/argo-cd` `stable` manifests — the
`applicationsets.argoproj.io` CRD is large enough that plain `kubectl apply` hits etcd's annotation size limit,
so it needs `--server-side`). It was pointed at `examples/argocd-live-validation/` in this repo (self-contained
so the test doesn't depend on another project's example-repo structure staying stable) — a classic App-of-Apps
(root `Application` with `source.directory.recurse: true`) and a real `ApplicationSet` (list generator), both
managing two trivial `pause` Deployments.

**What it found:**
- **A real bug affecting all 5 harnesses.** `kubectl get <kind> <name1> <name2> -o yaml` (naming 2+ resources in
  one call) wraps the result in a single `kind: List` document with an `items:` array, instead of the
  `---`-separated documents every harness's `load_docs()`/`main()` was written to expect. Every harness in this
  repo silently produced "no resources found" against output shaped exactly like the most natural way to dump
  multiple live resources with `kubectl`. Fixed by expanding `kind: List` into its `items` in all 5
  `harness/*.py` files.
- **A real usage caveat, not a bug.** The classic App-of-Apps signal (`source.directory.recurse: true`) lives
  entirely on the root `Application` — confirmed empirically, no `ownerReferences` are set on the children by a
  real Argo CD v3.4.5 controller, exactly as the earlier docs-based round concluded. But that also means if the
  root is excluded from what you feed `check_apps` (e.g. you only queried the apps your own team owns), the
  check has no way to tell two legitimately-managed children from two standalone one-off Applications, and will
  report FAIL. `fixtures/gitops/apps/live-argocd-appofapps-children-only.yaml` captures exactly this case and is
  asserted to fail on purpose — always include the root when auditing whether a set of apps is under App-of-Apps.
- **Confirmed, not just assumed.** The `ApplicationSet` controller genuinely stamps `ownerReferences` on the
  Applications it generates, pointing at the `ApplicationSet` — `fixtures/gitops/apps/live-argocd-applicationset-full.yaml`
  is a real capture of this, not hand-written.

### Namespace/Tenancy genericity validation (issue #3)

- **namespace (item 14)** was validated against the real Kustomize `namespace:` transformer field
  (`fixtures/namespace-tenancy/kustomize-real/`) and Helm's real `.Release.Namespace` built-in
  (`fixtures/namespace-tenancy/helm-real/`, rendered with and without an explicit `-n` flag — Helm genuinely
  defaults to `default` when it's omitted, which is exactly the anti-pattern). Both directions gave the
  expected verdict, no bugs found.
- **rbac (item 15)** was validated against the actual [ingress-nginx](https://github.com/kubernetes/ingress-nginx)
  Helm chart (pulled via its real Helm repo), which has a genuine `rbac.scope`/`controller.scope.enabled` toggle
  switching between cluster-wide RBAC (`ClusterRole`+`ClusterRoleBinding`, the chart's default) and
  namespace-scoped RBAC (`Role`+`RoleBinding`). Both variants were rendered with real `helm template` and
  committed as fixtures (`fixtures/namespace-tenancy/real-world/`). `check_rbac` correctly flags the
  cluster-wide default and passes the namespace-scoped variant — confirming the ClusterRole-vs-ClusterRoleBinding
  distinction the check relies on actually holds on a real, independently-authored chart, not just a fixture
  built to match the heuristic.

This closes the genericity-validation pass for every catalog item; all 15 items are now both implemented and
validated against real tooling (issues #1, #2, #3 above; items 1-6 and 11-13 validated in earlier rounds).

### Secrets genericity validation (issue #2)

- **exposure (item 9)** was validated against real `kustomize build` and `helm template` output
  (`fixtures/secrets/kustomize-real/`, `fixtures/secrets/helm-real/`) — it correctly flags the plain-value/
  ConfigMap-exposed cases and passes the `secretKeyRef` cases on genuinely rendered manifests, no bugs found.
- **plaintext (item 10)** was validated against the real schemas of both wrapper kinds mentioned in the
  catalog: [bitnami-labs/sealed-secrets](https://github.com/bitnami-labs/sealed-secrets) `SealedSecret`
  (`apiVersion: bitnami.com/v1alpha1`, `spec.encryptedData`, `spec.template.type`) and
  [external-secrets/external-secrets](https://github.com/external-secrets/external-secrets) `ExternalSecret`
  (`apiVersion: external-secrets.io/v1`, `spec.secretStoreRef`, `spec.target`, `spec.data[].remoteRef`) —
  confirmed via their docs/README examples. Both pass cleanly, and a genuine plain `kind: Secret` mixed into
  the same file alongside them is still caught. Notably `ExternalSecret` has no top-level `data`/`stringData`
  field the way a real `Secret` does (its `spec.data` only holds references into an external store, never
  the material itself), so the check's `kind == "Secret"` filter naturally avoids it without needing an
  explicit kind-exclusion list.

### Config-management genericity validation (issue #1)

- **env-parity (item 7)** was validated against a real Kustomize base + `overlays/{dev,staging,prod}`
  (`fixtures/config-mgmt/kustomize-real/`, using JSON6902 `patches:`) and a real minimal Helm chart +
  `values-{good,bad}-{dev,staging,prod}.yaml` (`fixtures/config-mgmt/helm-real/`). Both the "properly overridden"
  and "overlay exists but never patches host/API_URL" cases gave the expected verdict on genuinely rendered
  output — no bugs found in the check logic itself this round.
- **values-bloat (item 8)** was validated against a real public chart: the actual
  [ingress-nginx](https://github.com/kubernetes/ingress-nginx) `values.yaml`
  (`fixtures/config-mgmt/values-bloat/real-world/values.yaml`, 345 parameterized leaf keys, 1275 lines) with
  realistic per-env overrides (replica count, resources, autoscaling — 6 keys touched). The flattening/ratio
  logic handled the real file's complexity (deep nesting, empty dicts/lists, comments) without any parsing bugs.
  It did surface a real **limitation**, not a bug: the ratio metric can't distinguish a general-purpose,
  widely-reused OSS chart (which is *supposed* to expose far more knobs than any one consumer uses) from an
  in-house app chart that's bloated for no reason — both look identical to this check. The heuristic is only
  reliable today for charts a team actually authors for its own services, not third-party/vendored charts.

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

## License

This repo's own code is [MIT licensed](LICENSE). A handful of fixtures vendor real third-party files verbatim
for genericity testing (e.g. `fixtures/config-mgmt/values-bloat/real-world/values.yaml`, from
[kubernetes/ingress-nginx](https://github.com/kubernetes/ingress-nginx), Apache License 2.0) — each such file
says so and links its source in a header comment, and keeps its original license independent of this repo's.
