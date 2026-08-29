# Scaling the native well-founded solver

The `native` backend of
[`WellFoundedSolver`](wellfounded.md) is correct and dependency-free, but it is
deliberately simple and is **not** built for large programs. This page documents
*why*, and a phased plan to make it scale while keeping the same public API and
the same three-valued results.

The intent is that each phase is independently shippable, is a pure-Python
change until the very last one, and is validated against the current
implementation as a correctness oracle (see [Validation](#validation-strategy)).

## Where the time goes today

The native backend does three things, in `wellfounded_solver.py`:

1. **Grounding** (`_ground_rules`) — every rule is instantiated over the whole
   Herbrand universe by a naive cartesian product: `universe ** n_vars` ground
   instances per rule, *regardless of whether matching body facts exist*.
2. **Least model of a reduct** (`_gamma`) — forward chaining that re-scans every
   ground rule on every pass, with set-subset tests and no indexing.
3. **Alternating fixpoint** (`_alternating_fixpoint`) — iterates `γ²` to a least
   fixpoint (the true atoms) and to a greatest fixpoint (the non-false atoms),
   recomputing `γ` *from scratch* at every outer step.

The dominant costs, worst first:

| # | Bottleneck | Symptom |
|---|-----------|---------|
| A | Naive grounding (cartesian product) | Blows up with predicate arity / number of variables; grounds instances that can never fire |
| B | Naive least-model (no join index, no semi-naive) | Re-derives the whole relation every pass |
| C | Non-incremental alternating fixpoint | Recomputes the least model from `∅` at each outer iteration |
| D | Whole-program WFS | Runs the expensive three-valued machinery even where the program is stratified and a plain datalog pass would do |

## The plan

### Phase 0 — fail fast (safety, immediate)

Before optimizing, stop the naive grounder from silently OOMing. Add a guard that
estimates the ground-instance count and raises a clear error (with a pointer to
the `swi` backend / this page) once it exceeds a configurable budget. Cheap, and
turns a hang into an actionable message.

### Phase 1 — join-based, semi-naive evaluation (the big win, pure Python)

Replace both the cartesian grounding **and** the forward-chaining least-model
with standard bottom-up datalog evaluation:

- **Index facts** by `(predicate, bound-argument positions)` so rule bodies are
  evaluated as **relational joins** over the *current* extensions, producing only
  ground instances that actually have matching facts (output-sensitive instead of
  `universe ** n_vars`).
- **Semi-naive (differential) evaluation**: in each round join against only the
  newly-derived facts (the delta), not the whole relation. Positive recursion
  (transitive closure and friends) goes from "re-derive everything every pass" to
  work proportional to new derivations.

This subsumes bottlenecks **A** and **B** and is the single highest-leverage
change. It requires no new dependencies.

### Phase 2 — stratification / SCC decomposition

`undefined` only ever arises from a **cycle through negation**. So:

- Build the predicate dependency graph, tag edges that pass through
  negation-as-failure, and compute strongly connected components (Tarjan).
- Evaluate components in topological order. A component with **no negative cycle**
  is stratified: one semi-naive datalog pass with stratified negation gives its
  two-valued answer directly — **no alternating fixpoint needed**.
- Run the alternating fixpoint **only** on the residual non-stratified components.

This is "modular well-founded semantics": WFS cost collapses to datalog cost for
the stratified bulk, and the three-valued machinery is confined to the genuinely
ambiguous fragment (bottleneck **D**).

### Phase 3 — incremental / transformed alternating fixpoint

For the residual non-stratified components:

- **Warm-start** each `γ²` iteration from the previous interpretation instead of
  from `∅` (the lfp/gfp iterations are monotone), recomputing only affected atoms
  (bottleneck **C**).
- Alternatively, encode WFS as **two-valued datalog on a transformed (doubled)
  program**, so the semi-naive engine from Phase 1 computes the true and the
  non-false sets in a single evaluation, and the three-valued model falls out of
  their difference.

### Phase 4 — offload the core (only if still needed)

If pure Python is still the bottleneck at the target scale, delegate the
*stratified* core to a fast engine and keep only the WFS residual in Python:

- the existing [Souffle](souffle.md) integration, or a future Rust datalog engine
  (semi-naive joins + alternating-fixpoint outer loop, shipped as a
  `pip`-installable PyO3 wheel), or
- the [`swi` or `xsb`](wellfounded.md) backends for goal-directed / recursive workloads.

Phases 1–3 are expected to cover the vast majority of realistic programs without
reaching this phase.

## Boundaries (non-goals)

- **Function symbols / infinite Herbrand universes.** The bottom-up engine
  assumes a finite Herbrand base. Programs that generate unbounded terms are the
  domain of goal-directed tabling (SWI-Prolog, XSB), not this backend; the grounder should
  detect and reject them with a clear message rather than diverge.
- **API and semantics stay fixed.** Every phase lives behind `backend="native"`
  and must return byte-for-byte the same `(true, false, undefined)` partition as
  today. Scaling is an internal optimization, never a semantic change.

## Validation strategy

The current alternating-fixpoint implementation is the **reference oracle**:

- **Differential tests.** Every optimized path must produce the identical
  three-valued partition as the reference on a corpus of programs: stratified
  defaults, positive recursion (transitive closure), the even/odd negative loops,
  layered defaults, and disjunction-free ASP encodings.
- **Property-based tests.** Generate random normal logic programs (via
  `hypothesis`) and assert `optimized(program) == reference(program)`.
- **Benchmarks.** Track wall-clock and peak memory on transitive closure at
  increasing sizes, layered default reasoning, and negative-cycle-heavy programs,
  so each phase's win (and any regression) is measured, not assumed.
