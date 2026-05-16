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
