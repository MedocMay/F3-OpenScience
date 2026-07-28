**English** · [简体中文](INNOVATION.zh-CN.md)

# What Is Original Here

This file answers one question: **in F3-OpenScience, what is original and what is integrated?**

Separating the two is more useful than a blanket claim of "innovation" — and it is what the
project's own principles demand: do not count as yours what you did not do.

---

## 1. What is integrated (acknowledgements, not original)

| Capability | Source | What we did |
|---|---|---|
| Breadth: model-agnostic, many skills, scientific databases | [OpenScience](https://github.com/synthetic-sciences/openscience) (Apache-2.0) | Reused the design approach |
| Trustworthy delivery: cross-platform desktop, auditable workspace | [Open Science Desktop](https://github.com/ai4s-research/open-science) | Forked the shell layer |
| Dual persistent memory, recording successes and failures | EvoScientist (arXiv 2603.08127) | Reproduced the design (paper has no open implementation) |
| 4-layer citation verification + anti-fabrication | AutoResearchClaw (arXiv 2605.20025) | Reproduced the mechanism (own implementation, avoiding the licence) |
| Chain-of-evidence full-coverage gating | ScientistOne (arXiv 2605.26340) | Borrowed the idea, implemented independently |

**None of this is our invention.** Our work was assembling it into a whole that clears the
"you can sign your name to it" bar.

---

## 2. What is original: the reachability framework

The genuinely novel contribution centres on one problem:

> **When a system does "verify output → distil experience → constrain next generation,"
> the verifier's capability boundary quietly becomes the generator's world boundary.**

This self-destructive mechanism has not been clearly identified before, much less systematically
prevented. The following five points are original.

### Innovation 1 — Splitting the semantics of failure

Existing systems treat verification failure as a single signal. We show it must be split in two,
and that **only one kind earns the right to constrain generation**:

| Class | Meaning | May be written back as a generation constraint? |
|---|---|---|
| `fabrication` | An authoritative registry confirms non-existence — **the world disallows it** | ✅ |
| `verification_gap` | Index not covering it / criterion not applicable — **we simply cannot see it** | ❌ |

The criterion rests on the **authority of the evidence substrate**: arXiv IDs and DOI registries
are dense, authoritative spaces — a well-formed identifier that fails to resolve is fabrication.
An index like OpenAlex can only confirm; it **has no power to falsify**.

Implemented as one line:

```sql
inject()  WHERE lesson_class = 'fabrication'   -- verification gaps must not become generation constraints
```

**Key point**: the signing bar is not relaxed — both kinds of failure still block signing.
What changes is only whether a failure shapes generation preferences. Verification gaps become
`capability_backlog()` items (capability-building needs), not forbidden zones for generation.

### Innovation 2 — Migrating the judge from bibliography to computation and physics

If verification can only query databases, "reachable" will forever mean "has been indexed."
We pushed the criteria downward so that most of them **do not depend on any literature index**:

| Criterion | Authoritative source of denial | Index-dependent |
|---|---|---|
| arXiv / DOI registry | Confirmed non-existence | Yes |
| OpenAlex index | Coverage only; no power to deny | Yes |
| **Derivation recomputation** | The derivation contradicts the stated value | **No · computation** |
| **Dimensions / value range** | Accuracy > 1, incompatible dimensions | **No · physics** |
| **Domain physics** | Atoms not conserved, valence exceeded | **No · physics** |

`H2 + O2 -> H2O` failing atom conservation is pure arithmetic; `C2H8` having a degree of
unsaturation of −1 means hydrogen exceeds what the skeleton can carry.
**No database can change either.** This is where "reachability returns to physics" actually lands.

It also **expands** the reachable space: numbers no longer have to appear verbatim in the log —
they only have to be recomputable. What is relaxed is the *form* of evidence, not the burden of proof.

### Innovation 3 — Physical constraints reshape the proposal space up front

The dimensional check runs **before** evaluation in derivation discovery:

```python
ok, _ = dims.check_expression(expr, symbols)
if not ok: continue      # physically impossible combinations never enter the candidate set
```

This is not "fit freely, then filter afterwards" — it uses hard constraints to reshape the
search space itself.

### Innovation 4 — Honest metrics: three curves read together

Reporting only "interception rate is falling" cannot distinguish two things: the system learned
to stop fabricating, or it learned to dodge hard cases. Three curves must be read together:

```
interception↓ + reachability flat/↑ + exploration flat/↑  =  learning       genuinely improving
interception↓ + reachability↓                              =  narrowing      ⚠ routing around hard-to-verify areas
interception↓ + reachability flat + exploration↓           =  conservative   ⚠ only walking familiar paths
```

The third is the most insidious: every verification metric looks good, but the system has
stopped proposing low-prior hypotheses — degrading into a **safe, mediocre machine**.
The first two curves alone will never reveal it.

The accompanying **reachability regression set** (`tests/golden/reachability_case.json`)
deliberately collects claims that are "allowed by the world but easily killed by the verifier."
Its value is not a high score but exposing boundaries. Changes that raise
`false_rejection_rate` are not merged, **even if they raise the interception rate**.

### Innovation 5 — Novel claims signable on computational evidence

This closes a region that was previously entirely invisible: claims like "we propose that
mechanism X causes Y" — **actual scientific assertions** — were neither intercepted nor endorsed,
yet the system was signing off on drafts containing them.

Novelty determines **which evidence substrate is required**, not whether a claim passes:

```
supported by literature      →  citation or computational evidence both acceptable
absent from the index        →  computational evidence required (reproducible package / derivation / run log)
```

The second is not a relaxation but a switch to a **harder** substrate. This is what lets the
system take responsibility for "things not in the literature" instead of degrading into a
plagiarism checker.

Paired with an **exploration budget** (a mandatory quota for low-prior hypotheses), the system
actively moves toward regions the model does not favour — but exploration **does not lower the
evidence standard**: low-prior hypotheses must still pass the computational and physical judges.
Encouraging exploration without a physical judge only amplifies noise.

---

## 3. One methodological thread running through the project

During development the same epistemic error appeared once at **four different layers**:

| Layer | Form of the error |
|---|---|
| Infrastructure | The circuit breaker conflated HTTP 404 (the registry saying "no") with a network timeout (cannot connect) |
| Citation verification | Treating "OpenAlex cannot find it" as "this paper does not exist" |
| Dimensional inference | When text contained both *accuracy* and *improvement*, arbitrarily picking the former — judging a legitimate "12.4% improvement" as "probability above 1" |
| Domain criteria | The radical `CH3` has a half-integer degree of unsaturation — it genuinely exists and must not be ruled out |

All four are the same thing: **mistaking one's own observability boundary for the world's boundary.**

Hence the discipline running through the codebase:

> **Unknown means unknown — do not dress it up as known, and do not dress it up as impossible.**

Ambiguous semantics → make no assertion. Criterion not applicable → admit you cannot judge.
Library not installed → state explicitly "capability missing, not a physical conclusion."

We believe this methodology applies **beyond research agents** — any AI system with a
verification loop will encounter an isomorphic problem.

---

## 4. Reproducible verification

All of the following can be re-run directly from this repository (`make test`, 14 suites):

| Claim | How to verify |
|---|---|
| No fabricated citation passes the signing gate | `tests/test_coe.py` golden set, against live arXiv / CrossRef / OpenAlex |
| 0 false-rejection on 17 known-valid claims · 0 missed fabrication on 4 known-fabricated | `tests/test_reachability.py` — a 21-claim regression set; 11 of the valid claims are real papers the index does not cover (arXiv IDs recorded in `_provenance`, so the label is auditable) |
| Only fabrication constrains the flywheel | `tests/test_flywheel.py` + `test_reachability.py` |
| Derivation recomputation and contradiction detection | `tests/test_derivation.py` (includes AST whitelist safety tests) |
| Incompatible dimensions / value ranges | `tests/test_dimensions.py` |
| Mass conservation / valence limits | `tests/test_domains.py` (conservation criteria are dependency-free) |
| Three-curve verdict | `tests/test_exploration.py` |

**Please also read [STATUS.md](STATUS.md) — it lists explicitly what has not been verified.**
