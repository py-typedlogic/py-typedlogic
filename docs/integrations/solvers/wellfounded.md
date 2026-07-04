# Well-Founded Semantics Solver

The `WellFoundedSolver` computes the [well-founded model](https://en.wikipedia.org/wiki/Well-founded_semantics)
of a normal logic program (definite rules plus negation-as-failure). Unlike
Answer Set Programming, which enumerates zero or more two-valued *stable models*,
the well-founded semantics always yields exactly **one** three-valued model, in
which every ground atom is `true`, `false`, or `undefined`.

It ships three interchangeable backends, selected with the `backend` field:

- `native` (default) — a dependency-free pure-Python implementation of the Van
  Gelder alternating fixpoint. Returns the full three-valued model. Best for
  teaching and modestly-sized programs; it grounds naively and is not built for
  large programs (see [Scaling the native well-founded solver](wellfounded-scaling.md)
  for the plan to fix that).
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

## Installation

The `native` backend has no dependencies beyond `typedlogic` itself. The optional
backends reuse existing extras:

```bash
pip install typedlogic              # native backend only
pip install 'typedlogic[problog]'   # adds the problog backend
```

The `xsb` backend additionally requires the external
[XSB](https://xsb.sourceforge.net/) executable on `PATH`.

## Usage

### Reading the three-valued model

Load a theory (here in [TLog](../../conversion/parsers/tlog.md) syntax) and ask
for its model. The returned `WellFoundedModel` (documented below)
exposes the atoms that are **true** as `ground_terms` (so `iter_retrieve` works as
with any solver) and the atoms that are **undefined** as `undefined_terms`. Any
atom in neither list is **false**.

```python
from typedlogic.parsers.tlog_parser import TLogParser
from typedlogic.integrations.solvers.wellfounded import WellFoundedSolver

program = """
pred Bird(name: str).
pred Penguin(name: str).
pred Abnormal(name: str).
pred Flies(name: str).

Bird("tweety").
Bird("opus").
Penguin("opus").

Abnormal(x) :- Penguin(x).
Flies(x) :- Bird(x), not Abnormal(x).   # `not` is negation-as-failure
"""

solver = WellFoundedSolver()                 # backend="native" is the default
solver.add(TLogParser().parse(program))
model = solver.model()

print(sorted(str(t) for t in model.ground_terms))     # true atoms
print(sorted(str(t) for t in model.undefined_terms))  # undefined atoms
print([str(t) for t in model.iter_retrieve("Flies")]) # -> ['Flies(tweety)']
```

`tweety` flies (nothing proves it abnormal), `opus` does not (it is a penguin),
and this stratified program has no `undefined` atoms.

### Undefined atoms

Where a program loops through negation, the well-founded model marks the offending
atoms `undefined` instead of yielding several models (as ASP would) or none:

```python
loop = """
pred p().
pred q().
p() :- not q().
q() :- not p().
"""
solver = WellFoundedSolver()
solver.add(TLogParser().parse(loop))
model = solver.model()
print([str(t) for t in model.ground_terms])      # [] -- nothing is true
print(sorted(str(t) for t in model.undefined_terms))  # ['p', 'q']
```

### Building a theory programmatically

You can also assert predicate definitions, rules, and facts directly, using
`NegationAsFailure` for NAF body literals:

```python
from typedlogic import Term, NegationAsFailure, Variable, PredicateDefinition
from typedlogic.integrations.solvers.wellfounded import WellFoundedSolver

solver = WellFoundedSolver()
solver.add(PredicateDefinition(predicate="Bird", arguments={"name": "str"}))
solver.add(PredicateDefinition(predicate="Abnormal", arguments={"name": "str"}))
solver.add(PredicateDefinition(predicate="Flies", arguments={"name": "str"}))

x = Variable("x")
solver.add((Term("Bird", x) & NegationAsFailure(Term("Abnormal", x))) >> Term("Flies", x))
solver.add(Term("Bird", "tweety"))

print([str(t) for t in solver.model().iter_retrieve("Flies")])  # -> ['Flies(tweety)']
```

### Choosing a backend

```python
WellFoundedSolver()                     # native (default): full three-valued model
WellFoundedSolver(backend="problog")    # two-valued; raises NegativeCycleError on loops
WellFoundedSolver(backend="xsb")        # experimental; needs the xsb binary
```

`check()` always reports `satisfiable=True` (a well-founded model always exists),
and `models()` yields the single model.

::: typedlogic.integrations.solvers.wellfounded.WellFoundedSolver

::: typedlogic.integrations.solvers.wellfounded.WellFoundedModel

::: typedlogic.integrations.solvers.wellfounded.NegativeCycleError
