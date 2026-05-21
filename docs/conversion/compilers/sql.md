# SQL Compiler

::: typedlogic.compilers.sql_compiler.SQLCompiler

## Purpose

The SQL compiler translates a TypedLogic theory plus a query or goal into SQL.
It is intended for cases where logical predicates are backed by relational
tables and rule expansion should happen inside the database engine.

The design follows the same idea as Christoph Draxler's PL2SQL compiler, which
translated a projection term plus a Prolog database goal to SQL. Chris Mungall's
later TypedLogic-oriented experiments treated rules as database views so that
predicates defined by rules could be rewritten on demand. This compiler uses
common table expressions for that view layer:

- Extensional predicates are backed by configured tables or inline ground facts.
- Non-recursive Horn rules compile to ordinary CTE branches.
- Linear self-recursive rules compile to `WITH RECURSIVE`.
- Denial constraints compile to SQL queries that return violating rows.

Related modern systems include [Logica](https://logica.dev/), which compiles a
Datalog-family language to SQL engines; [Souffle](https://souffle-lang.github.io/tutorial),
which is a modern Datalog engine with database import/export support; and SQL
engines that expose recursion through recursive CTEs, such as
[Materialize](https://materialize.com/docs/sql/recursive-ctes/). Recent Datalog
surveys also emphasize rules as virtual relations or views for modular query
pipelines, e.g. [Modern Datalog: Concepts, Methods, Applications](https://drops.dagstuhl.de/storage/01oasics/oasics-vol138-rw2024%2Brw2025/html/OASIcs.RW.2024-2025.7/OASIcs.RW.2024-2025.7.html).

## Basic Usage

```python
from typedlogic import And, Forall, Implies, PredicateDefinition, Term, Theory, Variable
from typedlogic.compilers.sql_compiler import PredicateBinding, SQLCompiler

x = Variable("x")
y = Variable("y")
z = Variable("z")

theory = Theory(
    predicate_definitions=[
        PredicateDefinition("Parent", {"parent": "str", "child": "str"}),
        PredicateDefinition("Ancestor", {"ancestor": "str", "descendant": "str"}),
    ]
)
theory.add(Forall([x, y], Implies(Term("Parent", x, y), Term("Ancestor", x, y))))
theory.add(
    Forall(
        [x, y, z],
        Implies(And(Term("Ancestor", x, y), Term("Parent", y, z)), Term("Ancestor", x, z)),
    )
)

sql = SQLCompiler().compile(
    theory,
    goal=Term("Ancestor", "Alice", Variable("who")),
    bindings={
        "Parent": PredicateBinding(
            table="parent_edges",
            columns={"parent": "src", "child": "dst"},
        )
    },
)
```

The generated SQL uses the table binding for `Parent` and a recursive CTE for
`Ancestor`:

```sql
WITH RECURSIVE
Ancestor(ancestor, descendant) AS (
  SELECT _r0.src AS ancestor, _r0.dst AS descendant FROM parent_edges AS _r0
  UNION
  SELECT _r0.ancestor AS ancestor, _r1.dst AS descendant
  FROM Ancestor AS _r0, parent_edges AS _r1
  WHERE _r0.descendant = _r1.src
)
SELECT DISTINCT _q0.descendant AS who
FROM Ancestor AS _q0
WHERE _q0.ancestor = 'Alice'
```

## Table Bindings

Use `PredicateBinding` to bind logical predicate arguments to physical tables.
If `columns` is omitted, logical column names are used as physical names. If a
mapping is supplied, keys are logical argument names and values are physical SQL
columns.

```python
bindings = {
    "Parent": PredicateBinding("parent_edges", {"parent": "src", "child": "dst"}),
    "Person": "people",
}
```

Ground unit clauses do not need a binding. They compile to inline CTE branches:

```python
theory.add(Term("Person", "Alice"))
theory.add(Term("Person", "Bob"))
```

```sql
WITH
Person(name) AS (
  SELECT 'Alice' AS name UNION SELECT 'Bob' AS name
)
SELECT DISTINCT _q0.name AS x FROM Person AS _q0
```

## Goals And Queries

Pass an explicit `goal` to `compile` for goal-directed SQL:

```python
SQLCompiler().compile(theory, goal=Term("Person", Variable("x")))
```

If no explicit goal is passed, the compiler uses sentences in goal sentence
groups. Variables in the goal become projected SQL columns. Ground goals compile
to a boolean `holds` column using `EXISTS`.

## Constraints

First-order denial constraints compile to validation queries. A returned row is
a witness that violates the constraint.

```python
theory.add(Forall([x], Not(And(Term("Cat", x), Term("Dog", x)))))

queries = SQLCompiler().compile_constraints(
    theory,
    config=SQLCompilerConfig(
        bindings={"Cat": PredicateBinding("cats"), "Dog": PredicateBinding("dogs")}
    ),
)
```

```sql
SELECT DISTINCT _c1_0.name AS x
FROM cats AS _c1_0, dogs AS _c1_1
WHERE _c1_0.name = _c1_1.name
```

For portable SQL this is emitted as a violation query rather than a native
`CHECK`, because cross-table assertions and recursive validations are not
portable across SQL engines. Databases with assertion, trigger, or materialized
view support can wrap these queries in engine-specific enforcement.

## Supported Profile

The compiler targets a database-friendly fragment:

- Ground terms.
- Conjunctive queries and rule bodies.
- Horn rules generated from TypedLogic sentences.
- Positive relational atoms.
- Negation as correlated `NOT EXISTS`.
- Builtin binary comparisons: `eq`, `ne`, `lt`, `le`, `gt`, `ge`.
- Binary arithmetic expressions in rule heads or comparisons: `add`, `sub`,
  `mul`, `truediv`, `mod`.
- Linear self-recursive rules when `use_recursive_cte=True`.

The compiler intentionally raises `SQLTranslationError` for constructs that do
not have a portable relational translation, such as mutually recursive CTE
groups, unbound projected variables, non-conjunctive query bodies after Horn
normalization, and nested relation-valued function terms.

