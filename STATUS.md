**English** · [简体中文](STATUS.zh-CN.md)

# Project Status and Verification Boundary

> **This project was built under resource constraints and has not been comprehensively tested.**
> Please understand the boundaries below before deciding how to use it.

The existence of this file is itself part of the project's principles:
**unknown means unknown — do not dress it up as known.** We require the code to admit what it
cannot judge, so we must hold the project itself to the same standard.

---

## 1. Maturity

**This is a working research prototype, not a production-ready product.**

Suitable for:
- Studying the verification mechanism and the reachability framework
- Trial use and further development in a controlled environment
- Serving as a reference implementation for "verify + remember" systems

Not suitable (until the corresponding verification is done):
- Directly producing papers you will actually sign and publish
- Public multi-tenant service exposed to untrusted users
- Any critical scenario requiring strong correctness guarantees

---

## 2. What has been empirically tested

All of the following are reproducible in this repository (`make test`, 14 suites, all green):

| Item | How it was verified | Boundary |
|---|---|---|
| 4-layer citation verification | Against live arXiv / CrossRef / DataCite / OpenAlex | Golden set is small (single-digit samples) |
| Derivation recomputation + AST safety | Unit tests, including injection attempts | Operator space limited to 7 forms |
| Dimensional / range checks | Unit tests | Covers common ML/CS quantities; naming heuristics |
| Chemistry conservation / unsaturation / valence | Unit tests | C/H/N/O/halogens only; not validated against real chemistry workflows |
| Flywheel splitting and experience governance | End-to-end tests | Synthetic data, not real multi-user usage |
| Cross-user global aggregation | HTTP end-to-end | Multiple users simulated on one machine |
| Multi-process IPC (TS brain + Python sidecars) | Live run | — |
| Sandbox isolation (env scrubbing / rlimits / timeout) | Verified interception of memory bombs, infinite loops, key reads | Full only on Linux; see below |
| Service layer of all three deployment modes | Verified inside clean virtualenvs | Docker orchestration not run; see below |

---

## 3. What has **not** been verified (important)

### 🔴 Never run end-to-end with a real LLM

The development environment had no model API credentials. Therefore:

- The **model router**'s 8 providers were verified only for routing resolution and a local
  mock HTTP call. **Not one real cloud provider has ever been called.**
- The **LLM relevance scorer** (CoE layer 4) is implemented but has never been run against a real model.
- **The pipeline's "generation" stage is templated**, not real model output.
  `_EXPERIMENT` is a fixed-seed placeholder script that always emits 14.8%.

**This means: the verification, flywheel, and reachability mechanisms across the whole chain
are tested — but "an AI actually writing a research draft" has never been verified.**

### 🔴 Never produced an actual research result

The MVP acceptance criteria originally included "3–5 real ML topics producing signable drafts."
**That step was not done.** All testing used constructed claims and synthetic experiments.

So figures like "interception curve [1,0,0]" and "0 false-rejection rate" describe performance
**on our designed test set** and cannot be extrapolated to real research settings.

### 🟡 The desktop app builds, but has never been run

*Corrected 2026-07-25. This section previously said the shell had never been compiled;
that stopped being true once CI built it. 本节此前写「从未编译过」,CI 构建成功后该表述失效,已更正。*

- **Building works.** The v0.2.0 release workflow produced installers on
  ubuntu-22.04 (`.AppImage` / `.deb`), macos-latest (`.dmg`), and windows-latest (`.msi` / `.exe`).
- **Running has never been verified.** No one has installed any of those artifacts and
  opened the window. A successful compile says the Rust and frontend builds are sound;
  it says nothing about whether the UI works, whether the sidecars spawn correctly on a
  clean machine, or whether the splash-to-main handoff behaves.
- **Intel macOS has no prebuilt installer.** That CI runner can queue for hours and
  would block the whole release, so it is not built. Intel users must build locally.
- macOS `.dmg` files are **unsigned and un-notarised** — Gatekeeper will block them on a
  normal Mac. Windows installers are unsigned too, so SmartScreen will warn.
- The shell↔orchestrator IPC protocol was verified with a Node-based shell simulator,
  not with the real GUI.

### 🟡 Docker / orchestration layer has never run

- No Docker in the development environment. `compose.local.yml` / `compose.cloud.yml` /
  `compose.prod.yml` were only checked for YAML structure and dependency consistency —
  **`docker compose up` has never been executed.**
- The Postgres adapter is written to the same interface but was **only tested on the SQLite
  backend**; the Postgres path has never run.
- Same for Redis session externalization: code is ready, only the in-memory fallback was tested.
- Caddy automatic TLS is unverified.

### 🟡 Cross-platform: Linux only

- **Windows / macOS install and launch scripts were only statically checked** (syntax,
  placeholder substitution, structure) and have never run on real Windows or macOS.
- **On macOS `LocalSandbox` has no memory limit.** The kernel refuses `RLIMIT_AS`, so the
  512 MB ceiling silently does not exist. Until 2026-07-27 this also made `_preexec` raise and
  took the *whole* sandbox down — every run failed, on the maintainer own machine, and no
  documented command ran the suite that would have caught it. The sandbox now applies the
  limits it can and reports the rest via `SandboxResult.limits_unavailable`; the memory test
  skips with a stated reason. **Do not use `LocalSandbox` for multi-tenant or untrusted
  workloads on macOS** — use `ContainerSandbox`.
- macOS 上 `LocalSandbox` **没有内存上限**:内核拒绝 `RLIMIT_AS`。2026-07-27 之前这还会让
  `_preexec` 抛异常、整个沙箱瘫痪 —— 每一次执行都失败,就在维护者自己的机器上,而没有任何
  文档中的命令会跑到那个套件。**macOS 上不要把 `LocalSandbox` 用于多租户或不可信负载** ——
  请用 `ContainerSandbox`。
- On Windows the sandbox has **no memory or process-count limits** (POSIX `setrlimit` feature);
  it degrades to environment scrubbing + directory jail + timeout. Deploy on Linux for services
  exposed to untrusted users.
- Network isolation (`unshare -n`) is Linux-only.

### 🟡 Scale and performance entirely untested

- No stress testing, concurrency testing, or long-running tests.
- Experience-store behaviour at scale (indexing, decay, query performance) is unverified.
- Global service behaviour under real multi-tenant concurrency is unknown.
- No memory-leak or resource-usage analysis.

### 🟡 Security has not been independently audited

- The sandbox, AST-whitelist evaluation, BYOK vault, and multi-tenant isolation are **all
  self-tested** and have **not undergone third-party audit or penetration testing**.
- Derivation evaluation accepts model-generated expressions and is an explicit attack surface.
  We implemented whitelist protection and tested common bypasses, but **cannot guarantee no
  unknown bypass exists**.
- Audit it yourself before production, and follow the deployment checklist in [SECURITY.md](SECURITY.md).

### 🟡 Domain criteria coverage is very narrow

- Chemistry: only atom conservation, degree of unsaturation (C/H/N/O/halogens), and RDKit valence.
  **No** thermodynamic feasibility, kinetics, stereochemistry, or reaction conditions.
- Biology, materials, etc. are **entirely unimplemented** — only interfaces are reserved.

---

## 4. Known methodological limitations

Even within what is implemented, the following are **inherent design boundaries**, not bugs awaiting fixes:

1. **CoE does not judge whether causation holds.** It only verifies whether the evidence
   substrate is sound. Whether an experiment *sufficiently establishes* a mechanistic claim
   is reviewed by a human at the pre-signoff gate.

2. **Dimensional inference relies on naming heuristics.** These are not physical laws.
   We make it return `unknown` on ambiguity rather than deciding arbitrarily, but misses remain possible.

3. **Automatic derivation discovery is deliberately conservative.** It searches only 7 meaningful
   operators and gives up when precision is insufficient — it will miss legitimate derivations,
   but avoids fitting noise into "evidence." Authors can declare derivations explicitly.

4. **Insufficient index coverage and genuine novelty are indistinguishable on the evidence.**
   The system therefore reports only `unestablished_in_index` and never asserts `novel`.

---

## 5. What we hope the community will help verify

In order of value:

1. **Run it end-to-end with a real LLM** and report real false-rejection / missed-fabrication rates.
   A ready-made A/B harness for the core claim is in
   [`experiments/narrowing/`](experiments/narrowing/) — it currently uses a
   stand-in generator; swapping in a real model is the experiment that would
   turn the argument into a finding.
2. **Try it on real research topics** — we especially want cases where the verifier killed
   something real → please file a [false-rejection report](.github/ISSUE_TEMPLATE/false-rejection.yml)
3. **Build and try the desktop app** (requires the Rust toolchain)
4. **Deploy in a real Docker / Postgres / multi-tenant environment** and report problems
5. **Security audit**, especially the sandbox and derivation evaluation
6. **Extend domain criteria** (biology, materials), or point out errors in the chemistry criteria

---

## 6. Versioning commitments

- During 0.x, **the API is not guaranteed stable**; contracts may change in breaking ways (see [CHANGELOG.md](CHANGELOG.md))
- We will not relax assertions to make metrics look better
- Defects found will be recorded honestly in the changelog, including our own mistakes

---

*Last updated: v0.2.0 · If you find this file at odds with reality, that itself is worth an issue.*
