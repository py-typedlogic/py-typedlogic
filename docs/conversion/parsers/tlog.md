# TLog Parser

TLog is a compact text syntax for authoring TypedLogic theories without using
Python. It is still just another TypedLogic parser: the same `convert`, `dump`,
and `solve` commands work with it.

::: typedlogic.parsers.tlog_parser.TLogParser

::: typedlogic.parsers.tlog_parser.TLogMarkdownParser

## Syntax

```tlog
type PersonID: str.

pred parent(parent: PersonID, child: PersonID).
pred ancestor(ancestor: PersonID, descendant: PersonID).

parent("Alice", "Bob").
parent("Bob", "Charlie").

/// Direct parent links are ancestor links.
ancestor(x, y) :- parent(x, y).

/// Ancestor links are transitive.
ancestor(x, z) :- ancestor(x, y), ancestor(y, z).
```

Types are optional. Untyped targets can ignore them; typed targets such as
Souffle can use them.

## Predicate Arity Validation

Parsing is permissive: an *undeclared* predicate may be used at any arity, just
as Prolog treats `person/1` and `person/2` as distinct relations. Declaring a
predicate signals intent, so once a name is declared with `pred`, using it at an
arity that no declaration matches is reported as a validation error. This catches
a common mistake — writing a constraint against the wrong arity, which silently
refers to a different (empty) relation instead of the declared facts:

```tlog
pred foo(x: int, y: int).
foo(1, 1).
foo(1, 2).

/// BUG: foo/1 here is a different relation from the declared foo/2, so this
/// constraint is vacuously true and never contradicts the facts above.
all i, j | foo(i), foo(j) -> i = j.
```

Validation reports an error for the `foo/1` use. The intended functional-dependency
constraint compares the second column for a shared first column:

```tlog
all x, y1, y2 | foo(x, y1), foo(x, y2) -> y1 = y2.
```

If a name genuinely needs multiple arities, declare each one (`pred foo/1.` and
`pred foo(x: int, y: int).`). Errors surface through `parser.validate(...)`, the
CLI (e.g. `convert --validate-types`), or eagerly at parse time when the parser is
constructed with `auto_validate=True`.

Predicate and variable names are case-preserving. Variables are not inferred from
capitalization. In a rule or explicit quantifier, bare names are variables:

```tlog
ancestor(x, Y) :- parent(x, z), ancestor(z, Y).
```

In facts, bare names are constants:

```tlog
parent(Alice, Bob).
```

Use quoted strings when a constant appears in a rule body or head:

```tlog
favorite_child(x) :- parent("Alice", x).
```

## Quantifiers

Explicit universal and existential quantifiers are available:

```tlog
all x, y | parent(x, y) -> ancestor(x, y).
exists witness | observed(witness).
```

The classic symbols are accepted aliases:

```tlog
∀ x, y | parent(x, y) -> ancestor(x, y).
∃ witness | observed(witness).
```

If you need to disambiguate a variable without an explicit quantifier, use `?`:

```tlog
likes(?person, "tea") -> happy(?person).
```

## Quoted Meta Statements

Use `that(...)` to quote a sentence as data. Quoted sentences are not asserted
unless a runner explicitly interprets them.

Lemmas are named proof obligations:

```tlog
lemma(
  "grandparent_implies_ancestor",
  that(all x, y, z | parent(x, y) & parent(y, z) -> ancestor(x, z))
).
```

Test cases can carry quoted fixtures and expectations without sending them to
the solver as ordinary facts:

```tlog
test_case(
  "socrates_mortality",
  given(that(human("socrates"))),
  expect(that(satisfiable() & mortal("socrates") & not philosopher("socrates")))
).
```

`solve` ignores lemmas and test cases by default. Use `test` when you want a
one-stop validation command for both test cases and proof obligations; use
`prove` when you only want goals and lemmas:

```bash
typedlogic test theory.tlog --solver clingo
typedlogic prove theory.tlog --solver z3 --target lemmas
```

The test runner treats `given(that(S))` as a temporary assertion for that test
case. `expect(that(E))` checks the expected sentence. In expectations,
`satisfiable()` is a built-in check for fixture satisfiability, conjunction
means all expectations must hold, and `not P` means `P` is not entailed.
After running test cases, `test` also proves matching goals and lemmas unless
`--no-proofs` is used.

## HiLog-Style Predicate Variables

Use `@name(...)` to put a variable in predicate position:

```tlog
all slot, i, v | @slot(i, v) -> has_slot_value(i, slot).
```

This is useful for schema or macro-expansion layers. Backends that require fixed
first-order predicate names may reject such sentences until they are expanded.

## Literate Markdown

Markdown files ending in `.tlog.md` are parsed by `TLogMarkdownParser`. Prose is
ignored and fenced `tlog`, `typedlogic`, or `logic` blocks are parsed in order:

````markdown
# Family rules

Only this fenced block is parsed:

```tlog
pred parent(parent: str, child: str).
pred ancestor(ancestor: str, descendant: str).
ancestor(x, y) :- parent(x, y).
```
````

## CLI

The CLI auto-detects `.tlog` and `.tlog.md` files. Use `-f tlog` or
`-f tlogmarkdown` only when the suffix does not identify the format.

Convert TLog to another format:

```bash
typedlogic convert docs/examples/tlog/ancestor.tlog -t prolog
typedlogic convert docs/examples/tlog/ancestor.tlog -t yaml
typedlogic convert docs/examples/tlog/ancestor.tlog -t souffle
```

Convert any parser-supported input to TLog:

```bash
typedlogic convert docs/examples/tlog/ancestor.tlog -t tlog
```

Use `dump` when combining multiple input files or when you want pure
auto-detection:

```bash
typedlogic dump docs/examples/tlog/literate-rules.tlog.md -t prolog
```

Run inference with any installed solver:

```bash
typedlogic solve docs/examples/tlog/ancestor.tlog --solver clingo
```

Lemmas and test cases are metadata, so `solve` does not run or assert them.
Run validation explicitly with `test`:

```bash
typedlogic test docs/examples/tlog/mortality.tlog --solver clingo
typedlogic test docs/examples/tlog/mortality.tlog --solver clingo --test socrates_mortality
```

`test` also proves goals and lemmas by default. Use `prove` for proof-only runs:

```bash
typedlogic prove docs/examples/tlog/mortality.tlog --solver z3
typedlogic prove docs/examples/tlog/mortality.tlog --solver z3 --target lemmas
typedlogic prove docs/examples/tlog/mortality.tlog --solver z3 --name socrates_is_mortal
```

Show only selected materialized predicates:

```bash
typedlogic solve docs/examples/tlog/ancestor.tlog \
  --solver clingo \
  --show ancestor \
  --max-models 1
```

Show multiple answer sets:

```bash
typedlogic solve docs/examples/tlog/worlds.tlog \
  --solver clingo \
  --show selected \
  --max-models 2
```

The `--show` and `--max-models` options are generic `solve` options, not
TLog-specific commands.

Dump the generated solver program before solving:

```bash
typedlogic solve docs/examples/tlog/ancestor.tlog \
  --solver clingo \
  --dump-program
```
