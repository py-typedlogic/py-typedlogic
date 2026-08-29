# Reasoning about theories

The core data model carries *light syntactic types*: an argument declaration names a base
type or a defined type, and that is the whole of it. This is roughly the Souffle level of
expressiveness, and it is deliberate — the core stays close to Common Logic.

The optional metatheory adds a layer with a second-order flavour without changing the
core or introducing a second formalism. It works by reifying a theory into ordinary
ground facts, so that rules *about* types are ordinary first-order rules, run by whichever
solver you already use.

```
theory  ──reflection──▶  ground facts  ──┐
                                          ├──▶ solver ──▶ diagnostics
      metatheory axioms (@axiom) ─────────┘
```

## A first check

```python
from typedlogic import Theory
from typedlogic.datamodel import And, Forall, Implies, PredicateDefinition, Term, Variable
from typedlogic.theories.metatheory import check_theory

x = Variable("x")
theory = Theory(
    name="branded",
    type_definitions={"PersonID": "str", "OrgID": "str"},
    predicate_definitions=[
        PredicateDefinition("Person", {"id": "PersonID"}),
        PredicateDefinition("Org", {"id": "OrgID"}),
        PredicateDefinition("Flag", {"id": "PersonID"}),
    ],
)
theory.add(Forall([x], Implies(And(Term("Person", x), Term("Org", x)), Term("Flag", x))))

print(check_theory(theory))
```

```
Sentences: variable 'x' is used at positions declared 'OrgID' and 'PersonID', which are not compatible
```

`PersonID` and `OrgID` are both strings, so no signature is individually wrong. The
problem is that one variable spans both — a property of the rule, not of any declaration,
and exactly the kind of thing a per-argument type annotation cannot express.

## The three pieces

| Module | Role |
| --- | --- |
| `typedlogic.theories.metatheory.vocabulary` | Predicates describing a theory: signatures, type definitions, rule structure |
| `typedlogic.theories.metatheory.reflection` | Turns a `Theory` into ground facts of that vocabulary |
| `typedlogic.theories.metatheory.axioms` | The rules deriving subtyping, variable types, clashes, and stratification |

The axioms are plain `@axiom` functions. Nothing about them is privileged:

```python
@axiom
def type_clash(rule: RuleID, var: VarName, left: TypeName, right: TypeName):
    if VarType(rule, var, left) and VarType(rule, var, right) and -Compatible(left, right):
        assert TypeClash(rule, var, left, right)
```

## What it checks

- **`TypeClash`** — a variable used at two positions whose declared types are incompatible.
- **`ConstantClash`** — a literal at a position whose declared type cannot hold it.
- **`UndeclaredPredicate`** — a rule referencing a predicate the theory never declares.
- **`UnstratifiedNegation`** — a predicate on a recursive cycle passing through a negation.

The last one is the useful demonstration that this is not only about sorts. Stratification
is a property of the rule graph, and it falls out of the same machinery:

```python
@axiom
def unstratified_negation(p: PredicateName):
    if DependsNegatively(p, p):
        assert UnstratifiedNegation(p)
```

## Adding your own rules

Because the check *is* a solve, adding a rule adds a check. Write an `@axiom` over the
same vocabulary and pass the module in:

```python
@dataclass(frozen=True)
class UnbrandedArgument(Fact):
    predicate: PredicateName
    position: int

@axiom
def flag_unbranded_string_arguments(p: PredicateName, i: int):
    """An argument declared as a bare string carries no brand to enforce."""
    if ArgType(p, i, "str"):
        assert UnbrandedArgument(p, i)
```

```python
check_theory(theory, extra_axioms=[house_rules], extra_diagnostics=[UnbrandedArgument])
```

No change to the checker is needed. This is the practical payoff of keeping types as data
rather than as a fixed pass: project-specific conventions become enforceable without
forking the framework.

## Deliberate limits

**Descriptive, not prescriptive.** The checker reports what it can derive; it does not
require you to annotate anything. An unannotated theory is analyzed as far as its
declarations allow, and no further.

**Opaque types constrain nothing.** A type that does not resolve to a base type — an enum
class, or a name left over from an annotation the Python introspector could not reduce,
such as `Optional` — is treated as compatible with everything. Reporting an
incompatibility there would be reporting the checker's own ignorance.

**Reflection is partial.** Constructs the vocabulary cannot describe — arithmetic
subterms, builtin comparisons, sentences with no Horn form — are skipped rather than
approximated. A clean result is therefore bounded by what was skipped, which
`CheckResult.skipped` makes inspectable:

```python
result = check_theory(theory)
if result.ok and result.skipped:
    print(f"clean, but {len(result.skipped)} sentences were not analyzed")
```

## Negation: `-P` not `not P`

Inside an `@axiom`, `-P(...)` is negation as failure and `not P(...)` is classical
negation. They are not interchangeable. A classically negated body literal is lifted into
a head disjunction on the way to the solver, so an answer-set solver may satisfy the rule
by choosing the negated atom instead of your intended conclusion — a check written with
`not` reports whichever findings the chosen model happens to contain. Diagnostics need
"cannot be derived", which is what `-` means.

## Solver support

The default is Clingo, which supports the stratified negation the axioms use. The
negation is stratified by construction: `TypeClash` negates `Compatible`, which never
depends on `TypeClash`.

## Relation to mypy

The Python surface is checked by mypy, which is *prescriptive*: you declare, and code that
disagrees is rejected. The metatheory is *descriptive* and complements it, because the
properties above are invisible to mypy — it cannot see that a variable spans two
incompatible argument positions of a rule, nor that a rule set recurses through negation.
The two layers check different things, and neither subsumes the other.
