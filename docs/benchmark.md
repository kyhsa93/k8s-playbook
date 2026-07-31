# AI Manifest-Authoring Benchmark

This repo already has an objective scorer — the harness (`harness/check_*.py`) — that mechanically checks whether a Kubernetes manifest avoids the [documented anti-patterns](catalog.md), no human review needed. This doc defines how to reuse that scorer as a **benchmark for measuring an AI coding agent's ability to author Kubernetes manifests that follow this repo's documented conventions**, for a workload it's never seen before.

## Why this counts as a benchmark

A typical coding benchmark asks "does it pass the tests." This benchmark asks a different question — **"can the agent find and read this repo's documented anti-pattern catalog on its own, and apply it to a workload requirement it's never seen before, without being told which checks exist or how to satisfy them?"** The harness only scores *deployment configuration hygiene* (resource limits, probes, TLS, RBAC scope, autoscaling correctness, and so on) — not whether the workload's own application logic is correct, since there is none to check; the artifact under test is YAML, not code. That narrower scope is exactly what makes it mechanically scoreable with no human judgment call.

## Scope: which catalog items are scored

Only checks that can be scored from **one rendered manifest snapshot** are included — `scripts/score.sh` runs items 1-6 (workload/HA), 9-10 (secrets), and 14-19 (namespace/tenancy, networking, autoscaling). Items 7-8 (config-management, needs multiple per-environment renders) and 11-13 (GitOps-state, needs a declared/live pair or a full Warehouse/Stage pipeline) are out of scope for this version — see "How to extend this" below.

## Task format

The prompt given to the agent contains only these things — **it never explains how to implement it, and never names a specific check script or `docs/catalog.md` directly.**

1. A business/ops requirement for a workload **that doesn't exist anywhere in this repo's fixtures or docs yet** (never reuse a name already used for a past validation run — `payment-api`, `order-api`, and this doc's own example workload have all already become "seen" names once used; the next benchmark run picks a new one).
2. An instruction to "follow this repo's existing conventions," plus the minimal entry point for where to start reading (`README.md`) — no doc path beyond that is given. Whether the agent follows the doc index on its own to find `docs/catalog.md` and the harness scripts is itself part of what's being measured.
3. The completion criterion: an instruction to run `scripts/score.sh` against its own output and iterate until every applicable check passes.

## Scoring

```bash
scripts/score.sh <manifest.yaml>          # a single rendered/raw manifest file
kustomize build <dir> | scripts/score.sh -   # or pipe rendered Kustomize/Helm output
helm template <chart> | scripts/score.sh -
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

## How to extend this

- **A task suite by difficulty**: this first run asked for one workload needing
  ingress+autoscaling+secrets hygiene together. A harder level could require a second,
  related workload plus a GitOps deployment artifact (Argo CD `Application`/Flux
  `Kustomization`/Kargo `Stage`) to exercise items 11-13, or a Kustomize base +
  per-environment overlays to exercise items 7-8 — neither is scored by
  `scripts/score.sh` today.
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
