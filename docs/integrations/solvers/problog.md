# ProbLog Integrations

![problog logo](https://avatars.githubusercontent.com/u/2598157)

For auditable execution, use `ProbLogSolver(strict_compilation=True)`. Unsupported
assertions then raise `NotInProfileError` instead of being silently omitted or
rewritten by the legacy general-logic conversion. Invalid probability values,
non-Boolean evidence, and probability-wrapped compound formulas are rejected in
both modes. Inconsistent observations raise `UnsatisfiableEvidenceError` from
`model()`; `check()` reports `satisfiable=False`.

See the [ProbLog compiler](../../conversion/compilers/problog.md) for the accepted
subset, explicit negative evidence, and mutually exclusive annotated disjunctions.

::: typedlogic.integrations.solvers.problog.ProbLogSolver


