**English** · [简体中文](CONTRIBUTING.zh-CN.md)

# Contributing

Thank you for considering a contribution to F3-OpenScience.

This project is a **verification system for research output** — its entire value rests on
"can this judgement be trusted." Contribution discipline here is therefore stricter than usual,
especially for **verification logic**. Please read this first.

---

## One principle you must internalise

> **Unknown means unknown — do not dress it up as known, and do not dress it up as impossible.**

This is the project's epistemic baseline. It recurs throughout the code:

```
not found in the index      ≠  this paper does not exist
semantics unrecognisable    ≠  this value is physically impossible
library not installed       ≠  this structure is invalid
criterion not applicable    ≠  judged false
```

Treating "I cannot see it" as "the world disallows it" is the most serious class of defect in
this project — it teaches the system to route around hard-to-verify regions, degrading it into
a machine that only dares to say safe things.

**Every PR adding a criterion must answer: what happens when you cannot judge?**

See [docs/REACHABILITY.md](docs/REACHABILITY.md).

**Please read [STATUS.md](STATUS.md) before you start** — it lists what has not been verified,
which is also where contribution is most needed.

---

## Requirements for verification-logic contributions

When modifying decision logic under `coe_kernel/`, your PR must include:

1. **The authoritative source for the criterion**
   - Who has the right to declare "does not exist / impossible"? A registry, a computation, or a physical law?
   - Index-type data sources (e.g. OpenAlex) have **no** power to falsify — they can only confirm.

2. **Classified failure**
   - `fabrication` — confirmed contradiction; may constrain generation
   - `verification_gap` — insufficient capability/coverage; **must not** constrain generation

3. **A case in the reachability regression set**
   - `tests/golden/reachability_case.json`
   - False-rejection traps are especially welcome: claims "the world allows but the verifier
     easily kills." The value of this set is exposing boundaries, not scoring well.

4. **False-rejection rate must stay at 0**
   ```bash
   python3 tests/test_reachability.py
   ```
   A PR that raises `false_rejection_rate` will not be merged, **even if it raises the interception rate**.

---

## Development setup

```bash
git clone <your-fork>
cd F3-OpenScience
pip install -e '.[test]'                     # core is dependency-free; test group adds jsonschema
bash demo.sh                                 # smoke: verification kernel + flywheel + multi-process chain
```

Optional:
```bash
pip install -e '.[cloud]'                    # cloud: BYOK vault / Postgres / Redis
pip install -e '.[chem]'                     # chemistry valence checks (conservation/unsaturation need nothing)
cd orchestrator-ts && npm i                  # TS brain
cd apps/shell && npm i                       # desktop shell (also needs Rust)
```

## Running tests

```bash
make test                                    # all 14 suites
python3 tests/test_reachability.py           # reachability regression (mandatory when changing decision logic)
```

Some suites need network access (live arXiv / CrossRef / OpenAlex). They include reachability
guards: when an external API is unreachable they skip rather than fail.
**Please do not "fix" network flakiness by loosening assertions.**

## Changing contracts

`contracts/` is the single source of truth across languages. Workflow:

```bash
# 1. Edit contracts/*.schema.json
# 2. Regenerate both language bindings
bash scripts/gen-types.sh
# 3. Commit both contracts/ and generated/
```

Breaking changes (enum additions/removals, semantic changes) must include migration notes in `CHANGELOG.md`.

---

## Commit convention

Imperative mood, first line ≤ 72 characters:

```
verify: distinguish index gaps from confirmed fabrication
memory: inject only fabrication-class lessons into the flywheel
docs: document the applicability boundary of dimensional criteria
fix: stop counting 404 as a circuit-breaker failure
```

Prefixes: `verify` `memory` `pipeline` `model` `cloud` `deploy` `docs` `fix` `test` `chore`

## Pull requests

- One PR, one thing
- Include tests; changes to decision logic must include a reachability case
- Explain **how the change behaves when it cannot judge**
- CI must be green (contract validation + 14 suites + wheel build + TS typecheck)

## Reporting problems

- **False rejection** (something real judged as fabrication) — highest priority; please attach the full `verification_report`
- **Missed fabrication** (something fabricated passed) — equally high priority
- For security issues, **do not** open an issue — see [SECURITY.md](SECURITY.md)

## Code of conduct

Participation implies agreement with the [Code of Conduct](CODE_OF_CONDUCT.md).

## Licence

By contributing you agree to licence your code under [Apache-2.0](LICENSE).
