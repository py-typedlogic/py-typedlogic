# Changelog

## Unreleased

### Breaking

- **`not X` in an `@axiom` is now negation-as-failure.** It previously produced classical
  negation, the same node as `~X`. Classical/strong negation is now spelled `~X` only.

  This aligns the Python surface with the `.tlog` grammar, which has always read `not` and
  `\+` as NAF and `~` as classical, and with ASP-Core-2 (`not a` default negation, `-a`
  strong negation) and Prolog (`\+`, historically `not`). The two surfaces previously
  disagreed, and `docs/learning/semantics.ipynb` documented the TLog reading only.

  **Migration.** Replace `not X` with `~X` wherever you meant classical negation. The case
  that matters most is an integrity constraint in head position:

  ```python
  # before -- classical, asserts the conjunction cannot hold
  assert not (AncestorOf(x, y) and AncestorOf(y, x))
  # after
  assert ~(AncestorOf(x, y) and AncestorOf(y, x))
  ```

  Negation-as-failure in a rule body needs no change if you already wrote `-X` or
  `not_provable(X)`; `not X` now joins them.

  Scope: if you only target the Prolog or ProbLog backends, nothing changes at runtime —
  classical `Not` was already being rendered as `\+` there. The behavioural change affects
  the Prover9, TPTP, CLIF, Z3 and clingo paths.

- `-X` remains negation-as-failure and still works, but `not X` is now preferred. Note that
  `-` denotes *strong* negation in ASP, so the legacy spelling reads backwards to anyone
  arriving from clingo.

### Fixed

- `not_provable(P(x))` written in axiom source was parsed as a positive term rather than
  negation-as-failure, so rules using it silently never fired (see #58).
- `SouffleCompiler` emitted Prolog's `\+` for negation-as-failure instead of Soufflé's `!`
  (see #58).
