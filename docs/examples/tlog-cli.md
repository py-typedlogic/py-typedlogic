# TLog CLI Examples

TLog is a parser and compiler format, not a separate CLI mode. Use the existing
generic commands:

- `convert` for one input theory to one output format
- `dump` for combining and exporting inputs
- `solve` for satisfiability, materialization, and answer-set enumeration

## Convert TLog To Other Formats

```bash
typedlogic convert docs/examples/tlog/ancestor.tlog -t prolog
```

Example output:

```prolog
%% Predicate Definitions
% parent(parent: PersonID, child: PersonID)
% ancestor(ancestor: PersonID, descendant: PersonID)

parent('Alice', 'Bob').
parent('Bob', 'Charlie').
ancestor(X, Y) :- parent(X, Y).
ancestor(X, Z) :- ancestor(X, Y), ancestor(Y, Z).
```

Other compiler targets work the same way:

```bash
typedlogic convert docs/examples/tlog/ancestor.tlog -t yaml
typedlogic convert docs/examples/tlog/ancestor.tlog -t fol
typedlogic convert docs/examples/tlog/ancestor.tlog -t souffle
```

## Convert To TLog

Use `-t tlog` with any parser-supported input:

```bash
typedlogic convert docs/examples/tlog/ancestor.tlog -t tlog
```

Example output:

```tlog
type PersonID: str.

pred parent(parent: PersonID, child: PersonID).
pred ancestor(ancestor: PersonID, descendant: PersonID).

parent('Alice', 'Bob').
parent('Bob', 'Charlie').
/// Direct parent links are ancestor links.
all x, y | ancestor(x, y) :- parent(x, y).
/// Ancestor links are transitive.
all x, y, z | ancestor(x, z) :- (ancestor(x, y) & ancestor(y, z)).
```

## Literate Markdown

Files ending in `.tlog.md` are parsed as Markdown wrappers around fenced TLog
blocks:

```bash
typedlogic dump docs/examples/tlog/literate-rules.tlog.md -t prolog
```

The prose is ignored. Fenced `tlog`, `typedlogic`, or `logic` blocks are parsed
in order.

## Run Inference With Clingo

```bash
typedlogic solve docs/examples/tlog/ancestor.tlog \
  --solver clingo \
  --show ancestor \
  --max-models 1
```

Example output:

```text
Satisfiable: True

=== Model 1 ===
ancestor(Alice, Bob)
ancestor(Bob, Charlie)
ancestor(Alice, Charlie)

Total models shown: 1
```

`--show ancestor` filters materialized output to selected predicates. It is a
generic `solve` option and works for other syntaxes too.

## Show Multiple Worlds

Answer-set solvers such as Clingo can produce multiple models:

```bash
typedlogic solve docs/examples/tlog/worlds.tlog \
  --solver clingo \
  --show selected \
  --max-models 2
```

Example output:

```text
Satisfiable: True

=== Model 1 ===
selected(coffee)

=== Model 2 ===
selected(tea)

Total models shown: 2
```

The input syntax is still just TLog; the multiple-world behavior comes from the
chosen solver.
