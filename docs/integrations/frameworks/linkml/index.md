# LinkML Integration

![LinkML Logo](https://linkml.io/uploads/linkml-logo_color.png)

::: typedlogic.integrations.frameworks.linkml.loader

::: typedlogic.integrations.frameworks.linkml.reasoning

## Reasoning Architecture

The LinkML integration now uses two explicit logic layers.

First, the loader maps a LinkML schema to reified TBox facts such as
`class_definition/1`, `slot_definition/1`, `class_slot/2`, `slot_required/1`,
and `slot_range/2`. This loader does not generate ABox validation rules in
Python.

Second, the schema preprocessing layer is authored as literate TLog in
`src/typedlogic/integrations/frameworks/linkml/linkml_schema_rules.tlog.md`.
Those rules are ordinary clingo-compatible predicates. They materialize facts
such as `effective_class_slot/2`, `effective_range/3`, and normalized
cardinality constraints, and they reject schema-level errors such as `is_a`
cycles, missing parent classes, missing slot definitions, and inconsistent
cardinality bounds.

The compile-away layer then takes the materialized schema facts and emits direct
ABox rules. It assumes data has already been lowered to unary class/type
predicates and binary slot predicates:

```tlog
Person("p1").
name("p1", "n1").
string("n1").
```

For example, LinkML `required: true` plus `class_slot(Person, name)` compiles to
a closed-world aggregate constraint equivalent to:

```tlog
:- Person(i), { name(i, v) : name(i, v) } <= 0.
```

Slot ranges compile to constraints over unary range predicates:

```tlog
:- Person(i), age(i, v), not integer(v).
```

The HiLog-style intended macros are documented separately in
`src/typedlogic/integrations/frameworks/linkml/linkml_abox_macros.tlog.md`.
They are parseable TLog, but are not sent directly to clingo because clingo does
not support variable predicate position.

## CLI

LinkML schemas are still loaded through the generic parser path:

```bash
typedlogic dump schema.yaml -f linkml -t tlog
typedlogic convert schema.yaml -f linkml -t prolog
```

The direct ABox compile-away API is currently Python-facing:

```python
from typedlogic import Term
from typedlogic.integrations.frameworks.linkml.reasoning import validate_abox

validate_abox(
    schema,
    [
        Term("Person", "p1"),
        Term("name", "p1", "n1"),
        Term("string", "n1"),
    ],
)
```
