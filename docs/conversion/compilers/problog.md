# ProbLog Compiler

Use `ProbLogCompiler().compile(theory, strict=True)` when every asserted sentence
must either produce a supported clause or fail. `ProbLogSolver(strict_compilation=True)`
uses the same policy for execution and `dump()`.

The strict subset accepts positive atomic facts, universally quantified Horn rules
with one atomic head, conjunctive bodies, comparisons, explicit
`NegationAsFailure(atom)`, and explicit integrity constraints (`body >> Or()`).
Comparison heads such as `body >> (x != y)` become integrity constraints. Unsafe
head variables, existential sentences, general disjunctions, biconditionals,
top-level conjunctions, and classical `Not` in bodies are rejected with
`NotInProfileError`. Split deterministic conjunctions into separate asserted
sentences. For a closed-world body condition, use `NegationAsFailure`, rather than
assuming classical negation and negation as failure are interchangeable.
Head variables, including variables in function terms, must appear in positive
ordinary body atoms; comparisons alone do not establish this binding.
Anonymous head arguments (`None` or `Variable("_")`) are rejected, including
inside function terms.

Strict mode is opt-in to preserve existing general FOL conversion callers.
The default deterministic conversion remains best-effort and can omit or rewrite
unsupported forms; do not use it when clause coverage is required. Goals, lemmas,
and tests remain non-asserted theory metadata in both modes.

## Probabilities and evidence

In **both modes**, `Probability(p, That(...))` requires a finite numeric `p` in
`[0, 1]` (Booleans are not probabilities), and the wrapped sentence must be an
atomic fact or an atomic-headed Horn rule. A weighted conjunction or disjunction
is rejected: distributing its weight over multiple clauses introduces independent
choices and changes the probability model. To make several consequences share one
random cause, give a new atomic cause one probability and derive the consequences
with deterministic rules.

`Evidence(atom, value)` requires a ground positive atom and an actual Boolean.
`False` conditions on an observed negative; omitted evidence does not condition
on the atom. Strings such as `"false"` and integers such as `0` are rejected.
Unknown or unassessed observations should not be emitted as negative evidence.
The compiler rechecks raw `Term("Probability", ...)` and `Term("Evidence", ...)`
inputs as well as the typed constructors.

## Mutually exclusive choices

Use `AnnotatedDisjunction` for one categorical choice, rather than separate
independent probability facts:

```python
from typedlogic import Term, Theory
from typedlogic.extensions.probabilistic import AnnotatedDisjunction, Evidence
from typedlogic.integrations.solvers.problog import ProbLogCompiler

theory = Theory()
theory.add(AnnotatedDisjunction(((0.4, Term("GeneA")), (0.6, Term("GeneB")))))
theory.add(Evidence(Term("GeneA"), False))
theory.add(Term("query", Term("GeneB")))
program = ProbLogCompiler().compile(theory, strict=True, include_queries=False)
# 0.4::genea; 0.6::geneb.
# evidence(genea, false).
# query(geneb).
# P(geneb | not genea) = 1
```

Alternatives are `(probability, atom)` pairs with distinct atomic heads and a
total probability at most one. Heads must also remain distinct after Prolog
rendering (which lowercases predicates), and cannot contain anonymous arguments.
A total below one leaves the remaining probability
for none of the alternatives. An optional `body=...` supplies a Horn-rule body;
each grounding is a separate categorical choice. For example:

```python
from typedlogic import Variable
x = Variable("x")
choice = AnnotatedDisjunction(
    ((0.2, Term("A", x)), (0.3, Term("B", x))),
    body=Term("Person", x),
)
```

Exclusivity applies to this choice's contribution. Other facts/rules can still
derive either head, so avoid separately asserting competing hypotheses as facts.
This extension is supported by the ProbLog backend; it does not imply equivalent
semantics in the other backends or Python axiom parser.

## Auditing

Strict compilation checks the accepted syntax and prevents silently omitted
assertions. It does not establish that source extraction was complete or that
parameters and independence assumptions are justified. Sentence annotations are
metadata, not ProbLog comments or provenance output. Retain source identities and
rule identities in the originating application model, and generate its audit view
and executable clauses from the same source.

::: typedlogic.integrations.solvers.problog.ProbLogCompiler

