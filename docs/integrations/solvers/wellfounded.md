# Well-Founded Semantics Solver

The `WellFoundedSolver` computes the [well-founded model](https://en.wikipedia.org/wiki/Well-founded_semantics)
of a normal logic program (definite rules plus negation-as-failure). Unlike
Answer Set Programming, which enumerates zero or more two-valued *stable models*,
the well-founded semantics always yields exactly **one** three-valued model, in
which every ground atom is `true`, `false`, or `undefined`.

It ships three interchangeable backends, selected with the `backend` field:

- `native` (default) — a dependency-free pure-Python implementation of the Van
  Gelder alternating fixpoint. Returns the full three-valued model. Best for
  teaching and modestly-sized programs.
- `problog` — delegates to [ProbLog](problog.md), which evaluates the *two-valued*
  restriction of WFS. It agrees with `native` on stratified programs and raises
  `NegativeCycleError` on programs that are genuinely three-valued.
- `xsb` — **experimental, unverified.** Drives [XSB Prolog](https://xsb.sourceforge.net/),
  the reference SLG/tabling engine, as an external subprocess (requires the `xsb`
  executable on `PATH`). Intended for large or deeply-recursive programs, but it
  has not yet been validated against a live XSB install and is not exercised in
  CI; it emits a warning when used. Prefer `native` until it is validated.

For a worked comparison of the well-founded semantics against closed-world
Datalog and Answer Set Programming, see the
[semantics notebook](../../learning/semantics.ipynb).

::: typedlogic.integrations.solvers.wellfounded.WellFoundedSolver

::: typedlogic.integrations.solvers.wellfounded.WellFoundedModel

::: typedlogic.integrations.solvers.wellfounded.NegativeCycleError
