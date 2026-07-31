# AI Manifest-Authoring Benchmark

This repo already has an objective scorer — the harness (`harness/check_*.py`) — that mechanically checks whether a Kubernetes manifest avoids the [documented anti-patterns](catalog.md), no human review needed. This doc defines how to reuse that scorer as a **benchmark for measuring an AI coding agent's ability to author Kubernetes manifests that follow this repo's documented conventions**, for a workload it's never seen before.

## Why this counts as a benchmark

A typical coding benchmark asks "does it pass the tests." This benchmark asks a different question — **"can the agent find and read this repo's documented anti-pattern catalog on its own, and apply it to a workload requirement it's never seen before, without being told which checks exist or how to satisfy them?"** The harness only scores *deployment configuration hygiene* (resource limits, probes, TLS, RBAC scope, autoscaling correctness, and so on) — not whether the workload's own application logic is correct, since there is none to check; the artifact under test is YAML, not code. That narrower scope is exactly what makes it mechanically scoreable with no human judgment call.

## Scope: which catalog items are scored

`scripts/score.sh` is versioned by what submission shape it can accept, not by a flag — each version below is what the current script actually does, not a plan:

| Version | Items covered | Submission shape | Status |
|---|---|---|---|
| v1 | 1-6, 9-10, 14-19 (9 items) | one rendered manifest snapshot | shipped |
| v2 | + 12 (promotion) | v1's manifest + an optional second file, a Kargo `Stage` pipeline (`scripts/score.sh <manifest.yaml> [promotion-pipeline.yaml]`) | shipped |
| v3 | + 13 (apps) | v2's submission + a new app-registration file (`scripts/score.sh <manifest.yaml> [promotion-pipeline.yaml] [apps-registration.yaml]`), scored against `fixtures/benchmark/apps-context.yaml` as fixed pre-existing context | shipped |
| v4 | + 7-8 (config-mgmt) | a Kustomize base+overlays or Helm chart+per-env values directory, not a single manifest at all | scoped, not implemented |

**v3's design wrinkle, worth understanding before using it**: `check_apps` judges App-of-Apps/tree membership across the *whole* set of app resources it's handed, not the new one specifically. If the task simply handed the agent an existing tree that already satisfied the check on its own (e.g. an Argo CD `directory.recurse` root, whose children carry no distinguishing signal at all — see this repo's own live-Argo-CD/Flux findings above), the score would trivially PASS regardless of whether the agent's contribution was correct or even present. `fixtures/benchmark/apps-context.yaml` sidesteps this by being a single Flux `Kustomization` with no `dependsOn` of its own — by itself, or combined with a submission that ignores it, the set has zero tree signal. The only way to PASS is for the agent's new `Kustomization` to declare `dependsOn: [{name: infra}]`, correctly joining that existing resource — see the comment in that fixture for the full reasoning.

**Item 11 (drift) is permanently out of scope for this benchmark, not a future version.** Drift is a live-cluster-vs-Git divergence signal — it only exists when someone (or something) changes a running cluster out-of-band *after* a manifest was authored and applied. An authoring benchmark scores what an agent writes; it structurally cannot produce or avoid drift, so there is no version of this benchmark that could ever score item 11. The ceiling for this benchmark, once v4 is built, is **18/19 applicable items**, not 19/19 — v1-v3 already cover 12 of those 18.

## Task format

The prompt given to the agent contains only these things — **it never explains how to implement it, and never names a specific check script or `docs/catalog.md` directly.**

1. A business/ops requirement for a workload **that doesn't exist anywhere in this repo's fixtures or docs yet** (never reuse a name already used for a past validation run — `payment-api`, `order-api`, and this doc's own example workloads have all already become "seen" names once used; the next benchmark run picks a new one).
2. An instruction to "follow this repo's existing conventions," plus the minimal entry point for where to start reading (`README.md`) — no doc path beyond that is given. Whether the agent follows the doc index on its own to find `docs/catalog.md` and the harness scripts is itself part of what's being measured.
3. The completion criterion: an instruction to run `scripts/score.sh` against its own output and iterate until every applicable check passes. If the task is also meant to exercise item 13, the agent is told its new app-registration file will be scored alongside "the existing apps this cluster already manages" — `fixtures/benchmark/apps-context.yaml` itself is never named directly, same as `docs/catalog.md` isn't.

## Scoring

```bash
scripts/score.sh <manifest.yaml>                              # a single rendered/raw manifest file
kustomize build <dir> | scripts/score.sh -                    # or pipe rendered Kustomize/Helm output
helm template <chart> | scripts/score.sh -
scripts/score.sh <manifest.yaml> <promotion-pipeline.yaml>    # v2: also score item 12 (Kargo Stage pipeline)
scripts/score.sh <manifest.yaml> <promotion.yaml> <apps.yaml> # v3: also score item 13 (new app joins fixtures/benchmark/apps-context.yaml)
scripts/score.sh <manifest.yaml> "" <apps.yaml>               # v3 without a promotion pipeline: pass an empty string to skip item 12
```

- **Output**: one `[PASS]`/`[FAIL]`/`[N/A]` line per scoring unit, plus a summary
  (`Score: X/Y applicable checks passed (Z N/A excluded)`). A unit is `[N/A]`, not a
  miss, when the relevant kind (Ingress, HorizontalPodAutoscaler) is entirely absent
  from the submission — a workload that has no legitimate need for autoscaling or
  external ingress shouldn't be penalized for lacking one. It's excluded from the score
  denominator entirely, the same principle BSP's benchmark harness uses.
- **The scorer must be the person running the benchmark, not the agent itself.** Don't
  just trust the agent's self-report of "score.sh passes clean" — independently rerun
  `scripts/score.sh` against the agent's actual output, and read the manifest directly
  to confirm it's a genuine, sensible answer to the requirement rather than something
  that games the checks (e.g. an Ingress with a `tls:` block pointing at a `secretName`
  that doesn't correspond to anything real, just to satisfy item 17's presence check).

## Run — a single case

Actually ran once. Task: add a **`notification-gateway`** workload — an HTTP service that sends
push notifications, has bursty traffic (spikes during marketing campaigns), needs a third-party
provider API key supplied via configuration, and must be reachable over HTTPS from outside the
cluster at `notifications.example.com`. The agent was given only this requirement and told to start
from `README.md` — `docs/catalog.md` and no individual `harness/check_*.py` file were ever named;
`scripts/score.sh` was named directly as the completion-criterion tool (matching how BSP names
`harness.sh` but never `docs/reference.md`/its scaffolding generator).

**A repo-setup quirk the agent had to work around, not a bug in its manifest.** `scripts/score.sh`
had been written earlier the same session but not yet committed when the agent was spawned — a
fresh `git worktree` only shares committed history, not the parent checkout's uncommitted working
directory, so the file legitimately didn't exist in the agent's worktree. The agent noticed,
diagnosed it correctly (`git log --all -- scripts/score.sh` empty on `main`/`origin/main`), copied
the file's exact content from the shared main checkout without modifying anything there, and used
that copy purely to self-score — it never committed it. Worth calling out because it's exactly the
kind of "trust but verify" situation this doc says not to skip: the fix here was to independently
rerun the *canonical, actually-committed* `scripts/score.sh` from the main checkout against the
agent's output, not to just accept that its self-copied version agreed with itself.

**Result**: the agent produced 9 resources (`Namespace`, `ConfigMap`, `SealedSecret`, `Deployment`,
`Service`, `Ingress`, `NetworkPolicy`, `PodDisruptionBudget`, `HorizontalPodAutoscaler`) and reported
`Score: 9/9 applicable checks passed`. Independently rerunning the real `scripts/score.sh` against
the agent's actual manifest file from the main checkout reproduced the identical result —
**9/9, matching exactly**. Reading the manifest directly (not just the score) confirmed it's a
genuine, sensible answer rather than something gaming the checks: the API key is a `SealedSecret`
consumed via `secretKeyRef` (not a plaintext value chosen just to dodge item 9/10), the `NetworkPolicy`
is a real default-deny-plus-explicit-allow (ingress scoped to the `ingress-nginx` namespace, egress
scoped to DNS+443 for the actual third-party call the requirement described — not a rule that merely
exists to satisfy item 16's presence check), and the HPA's wide `3-30` range plus an asymmetric
`behavior` block (instant scale-up, gradual scale-down) is a considered answer to "bursty campaign
traffic," not a boilerplate copy of an existing fixture's numbers.

This run demonstrated the same two things BSP's first run did: (1) `scripts/score.sh` works as a
trustworthy scorer against a genuinely novel requirement, and (2) this repo's doc structure
(`README.md` → `docs/catalog.md` → the relevant `fixtures/*/good-*.yaml` examples) is organized well
enough for an agent, not just a human, to find and apply on its own without being told which files
to look at.

## Run — comparing models (Sonnet vs Haiku)

Task: add a **`shipment-tracker-api`** workload — an internal-only HTTP service (no external
exposure) tracking parcel shipments, with bursty nightly-batch traffic, a database credential
supplied via configuration, and a required dev→staging→prod promotion pipeline with a
verification gate at each step (added specifically to exercise v2's new item 12 scoring).
Two agents, identical prompt, `isolation:"worktree"`, one on Sonnet and one on Haiku, spawned
after committing the v2 `score.sh` change (avoiding the uncommitted-scorer detour from the run
above).

**Both self-reported `9/9 applicable checks passed (1 N/A excluded)`, independently reproduced
exactly against each agent's actual files from the main checkout.** Unlike BSP's
Sonnet-vs-Haiku round (SavingsPocket domain), which found a clean pass/fail gap (6/6 vs 3/3),
this run's harness score alone shows no difference between the two models at all.

Reading both submissions directly surfaced two real quality differences the harness cannot
see — one favoring each model, not a clean win either way:

- **Sonnet's `NetworkPolicy` has a self-defeating ingress rule.** Alongside a correctly-scoped
  rule allowing only the assumed webhook-gateway namespace, it added a second ingress rule with
  `namespaceSelector: {}` — which Kubernetes matches against *every* namespace, not "other
  internal services" as its own comment claimed. That makes the first, narrower rule pointless:
  the policy as written accepts traffic from any pod in any namespace on port 8080, which is a
  real least-privilege violation `check_networking.py`'s `netpol` check can't detect (it only
  checks that *a* `NetworkPolicy` exists in the namespace, not that its rules are actually
  scoped). Haiku's ingress rules name exactly two namespaces (`batch-jobs`, `order-processing`)
  with no such catch-all.
- **Haiku's promotion pipeline is more complete and closer to actually deployable.** This
  repo's own `fixtures/gitops/promotion/good.yaml` (the fixture nearest `docs/catalog.md`, and
  what `check_promotion` is validated against) only contains `Stage` resources — deliberately
  minimal, since it exists purely to be scored. A real Kargo pipeline also needs a `Warehouse`
  (the actual freight source `Stage.spec.requestedFreight[].origin` points at) and typically a
  `Project`, both present in the deeper `examples/kargo-live-validation/kargo-resources.yaml`.
  Sonnet's `promotion/pipeline.yaml` mirrors the minimal Stage-only fixture — it passes
  `check_promotion` but references a `Warehouse` named `shipment-tracker-api` that is never
  defined anywhere in its submission, so the pipeline as delivered would never actually
  discover freight on a real cluster. Haiku's `promotion-pipeline.yaml` includes the matching
  `Project` and `Warehouse`, i.e. it read further into the repo's docs than the minimum needed
  to satisfy the scorer and produced something that would actually work if applied.
- Also notable, though not scored either: Haiku's container `securityContext` adds
  `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`, and `capabilities.drop:
  [ALL]` on top of `runAsNonRoot` — a fuller answer to catalog item 4's "least privilege" than
  Sonnet's pod-level `runAsNonRoot: true` alone. `check_workload.py` only checks for
  `runAsNonRoot`, so this difference is invisible to the score too.

**Takeaway**: a tied structural score does not mean tied output quality in either direction —
it means the harness's blind spots need to be checked by hand every time, regardless of which
model is being evaluated or how the two scores compare.

## How to extend this

- **v4 (items 7-8, config-mgmt)**: change the submission shape entirely — a Kustomize
  base+overlays or Helm chart+per-env values directory instead of one file. `scripts/score.sh`
  would need a directory-aware invocation (render each env with `kustomize build`/`helm
  template` before handing the result to `check_config_mgmt.py env-parity`/`values-bloat`),
  which is a bigger change than v2/v3's optional-extra-file pattern.
- **A task suite by difficulty**: so far every run has asked for one workload's worth of
  hygiene (v1), hygiene + a promotion pipeline (v2), or hygiene + promotion + App-of-Apps
  registration (v3). Once v4 exists too, a harder level could combine all of them in one
  task — a new workload needing hygiene, a promotion pipeline, tree registration, and
  per-env overlays at once.
- **Comparing across models**: run the identical task prompt with a different model and
  compare the independently-reverified scores — mirrors
  [backend-service-playbook's benchmark](https://github.com/kyhsa93/backend-service-playbook/blob/main/docs/benchmark.md)
  finding that a perfect structural score doesn't guarantee the artifact actually works
  as claimed.
- **Regression watch**: rerunning the same task whenever the catalog or harness changes,
  confirming the score doesn't drop, catches whether a docs/harness change accidentally
  made the conventions harder for an agent to follow on its own.

## Related docs

- `docs/catalog.md` — the anti-pattern catalog itself, the only thing a benchmark task
  expects the agent to discover and read on its own (via `README.md`'s own doc index)
- `harness/check_*.py` — the individual checks `scripts/score.sh` aggregates; never
  named directly in a benchmark prompt — discovering them is part of what's measured
- `fixtures/benchmark/apps-context.yaml` — the fixed pre-existing app tree v3 (item 13)
  scores a new submission against; never named directly in a benchmark prompt either
