# Anti-Pattern ↔ Correct Pattern Catalog

Each entry consists of three parts: the anti-pattern, its correct-pattern counterpart, and how the harness verifies it. Wherever possible, the harness checks the **final rendered K8s object**, so it works the same whether the manifest came from raw YAML, Kustomize, or Helm.

## 1. Workload Definition

| # | Anti-Pattern | Correct Pattern | Harness Check | Status |
|---|---|---|---|---|
| 1 | resource requests/limits missing | requests/limits sized for the workload (critical=Guaranteed QoS, general=Burstable) | parse every container spec for `resources.requests`/`limits` | implemented |
| 2 | image tag is `:latest` or missing | pin an immutable tag (semver or digest) | regex the `image` field for `:latest` / missing tag | implemented |
| 3 | liveness/readiness probe missing, or both probes share the same endpoint | separate startup/liveness/readiness roles with distinct endpoints | check probe fields exist + compare endpoints | implemented |
| 4 | container runs as root, or `privileged: true` | `securityContext.runAsNonRoot: true` + least privilege | parse securityContext fields | implemented |

## 2. Availability / HA

| # | Anti-Pattern | Correct Pattern | Harness Check | Status |
|---|---|---|---|---|
| 5 | critical service has replicas=1, no PodDisruptionBudget | replicas≥2 + a defined PodDisruptionBudget | check `replicas` value, look for a matching PDB resource (matched by selector labels) | implemented |
| 6 | no pod anti-affinity, all replicas land on one node | `podAntiAffinity` spreads replicas across nodes/AZs | check for affinity field | implemented |

## 3. Configuration Management

| # | Anti-Pattern | Correct Pattern | Harness Check | Status |
|---|---|---|---|---|
| 7 | environment-specific values (domain, replica count, etc.) hardcoded into the base manifest | Base + Overlay (Kustomize) or base chart + per-env values (Helm) | diff renders across environments; flag env-specific values baked into the base | planned |
| 8 | Helm `values.yaml` parameterizes every field, causing complexity blowup ("god values file") | only parameterize values that actually vary per environment | measure values.yaml schema size vs. actual per-env override ratio | planned |

## 4. Secrets

| # | Anti-Pattern | Correct Pattern | Harness Check | Status |
|---|---|---|---|---|
| 9 | secret values exposed via ConfigMap or plain env vars | reference a `Secret` resource (`secretKeyRef`/`envFrom`) | scan ConfigMap/env values for secret-like keywords (password, token, key) | planned |
| 10 | plaintext secrets committed to the Git repo | commit only encrypted forms (Sealed Secrets, External Secrets Operator, etc.) | scan the repo for plaintext Secret manifests | planned |

## 5. Deployment / Sync (GitOps)

| # | Anti-Pattern | Correct Pattern | Harness Check | Status |
|---|---|---|---|---|
| 11 | manual `kubectl apply` used alongside a running GitOps controller | every change goes through a Git commit; no direct cluster edits | diff live cluster state vs. declared Git state — any drift is evidence of the violation | implemented |
| 12 | a dev change reaches prod with no verification gate | promote through dev→staging→prod with health checks/tests at each stage (e.g., Kargo) | check that each non-entry Stage definition has verification conditions | implemented |
| 13 | applications registered and managed one by one, by hand | manage declaratively via App of Apps (Argo CD, `directory.recurse`), ApplicationSet, or a Kustomization tree (Flux, `dependsOn`) | check for a directory-recursion root, ApplicationSet ownership, or a Flux dependsOn tree | implemented |

## 6. Namespace / Tenancy

| # | Anti-Pattern | Correct Pattern | Harness Check | Status |
|---|---|---|---|---|
| 14 | every workload lives in the `default` namespace | separate namespaces per team/environment | check whether `namespace` is `default` | planned |
| 15 | no namespace-scoped RBAC, cluster-wide permissions granted instead | least-privilege Role/RoleBinding scoped to the namespace | check for ClusterRole(Binding) usage vs. namespace-scoped RBAC | planned |

---

Use this catalog as the checklist for building the harness against the minimal fixture (raw manifest) first. As Kustomize/Helm/Argo CD/Flux fixtures are added, re-run the same checklist to confirm each item is detected identically regardless of tool.
