"""Tests for SQL compilation from TypedLogic theories."""

# ruff: noqa: S101

import sqlite3

from typedlogic import And, Forall, Implies, Not, PredicateDefinition, Term, Theory, Variable
from typedlogic.compilers.sql_compiler import PredicateBinding, SQLCompiler, SQLCompilerConfig
from typedlogic.datamodel import NegationAsFailure, SentenceGroup, SentenceGroupType
from typedlogic.registry import all_compiler_classes, get_compiler


def fetchall(sql: str, setup: list[str] | None = None) -> list[tuple]:
    """Execute SQL against an in-memory SQLite database."""
    connection = sqlite3.connect(":memory:")
    try:
        for statement in setup or []:
            connection.execute(statement)
        return list(connection.execute(sql))
    finally:
        connection.close()


def test_sql_compiler_is_registered():
    """SQLCompiler is discoverable through the compiler registry."""
    assert "sql" in all_compiler_classes()
    assert isinstance(get_compiler("sql"), SQLCompiler)


def test_ground_unit_clauses_compile_to_inline_relation():
    """Ground facts are usable without external table bindings."""
    x = Variable("x")
    theory = Theory(predicate_definitions=[PredicateDefinition("Person", {"name": "str"})])
    theory.add(Term("Person", "Alice"))
    theory.add(Term("Person", "Bob"))

    sql = SQLCompiler().compile(theory, goal=Term("Person", x))

    assert set(fetchall(sql)) == {("Alice",), ("Bob",)}


def test_keyword_terms_follow_declared_column_order():
    """Keyword terms are projected in predicate-definition order."""
    x = Variable("x")
    y = Variable("y")
    theory = Theory(predicate_definitions=[PredicateDefinition("Pair", {"left": "str", "right": "str"})])
    theory.add(Term("Pair", {"right": "B", "left": "A"}))

    sql = SQLCompiler().compile(theory, goal=Term("Pair", x, y))

    assert fetchall(sql) == [("A", "B")]


def test_configurable_table_binding_and_nonrecursive_rule():
    """Predicate bindings map logical arguments to physical SQL columns."""
    x = Variable("x")
    y = Variable("y")
    theory = Theory(
        predicate_definitions=[
            PredicateDefinition("Person", {"name": "str"}),
            PredicateDefinition("Parent", {"parent": "str", "child": "str"}),
        ]
    )
    theory.add(Forall([x, y], Implies(Term("Parent", x, y), Term("Person", x))))

    sql = SQLCompiler().compile(
        theory,
        goal=Term("Person", x),
        bindings={"Parent": PredicateBinding("parent_edges", {"parent": "src", "child": "dst"})},
    )

    rows = fetchall(
        sql,
        [
            "CREATE TABLE parent_edges (src TEXT, dst TEXT)",
            "INSERT INTO parent_edges VALUES ('Alice', 'Bob'), ('Alice', 'Carol'), ('Bob', 'Dana')",
        ],
    )
    assert set(rows) == {("Alice",), ("Bob",)}


def test_recursive_rules_compile_to_recursive_cte():
    """Linear recursion is emitted as WITH RECURSIVE and executed by SQLite."""
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
    theory.add(Forall([x, y, z], Implies(And(Term("Ancestor", x, y), Term("Parent", y, z)), Term("Ancestor", x, z))))

    sql = SQLCompiler().compile(
        theory,
        goal=Term("Ancestor", "Alice", Variable("who")),
        bindings={"Parent": PredicateBinding("parent_edges", {"parent": "src", "child": "dst"})},
    )

    rows = fetchall(
        sql,
        [
            "CREATE TABLE parent_edges (src TEXT, dst TEXT)",
            "INSERT INTO parent_edges VALUES ('Alice', 'Bob'), ('Bob', 'Carol'), ('Carol', 'Dana')",
        ],
    )
    assert "WITH RECURSIVE" in sql
    assert set(rows) == {("Bob",), ("Carol",), ("Dana",)}


def test_negation_as_failure_compiles_to_not_exists():
    """Negated body atoms become correlated NOT EXISTS predicates."""
    x = Variable("x")
    theory = Theory(
        predicate_definitions=[
            PredicateDefinition("Person", {"name": "str"}),
            PredicateDefinition("Blocked", {"name": "str"}),
            PredicateDefinition("Eligible", {"name": "str"}),
        ]
    )
    theory.add(Forall([x], Implies(And(Term("Person", x), NegationAsFailure(Term("Blocked", x))), Term("Eligible", x))))

    sql = SQLCompiler().compile(
        theory,
        goal=Term("Eligible", x),
        bindings={"Person": "people", "Blocked": "blocked"},
    )

    rows = fetchall(
        sql,
        [
            "CREATE TABLE people (name TEXT)",
            "CREATE TABLE blocked (name TEXT)",
            "INSERT INTO people VALUES ('Alice'), ('Bob')",
            "INSERT INTO blocked VALUES ('Bob')",
        ],
    )
    assert "NOT EXISTS" in sql
    assert rows == [("Alice",)]


def test_fol_denial_constraint_compiles_to_violation_query():
    """A first-order denial constraint returns witnesses that violate it."""
    x = Variable("x")
    theory = Theory(
        predicate_definitions=[
            PredicateDefinition("Cat", {"name": "str"}),
            PredicateDefinition("Dog", {"name": "str"}),
        ]
    )
    theory.add(Forall([x], Not(And(Term("Cat", x), Term("Dog", x)))))
    config = SQLCompilerConfig(bindings={"Cat": PredicateBinding("cats"), "Dog": PredicateBinding("dogs")})

    [sql] = SQLCompiler().compile_constraints(theory, config=config)

    rows = fetchall(
        sql,
        [
            "CREATE TABLE cats (name TEXT)",
            "CREATE TABLE dogs (name TEXT)",
            "INSERT INTO cats VALUES ('Jules'), ('Milo')",
            "INSERT INTO dogs VALUES ('Milo'), ('Rex')",
        ],
    )
    assert rows == [("Milo",)]


def test_theory_goals_compile_when_no_explicit_goal_is_passed():
    """The compiler uses goal sentence groups as default queries."""
    x = Variable("x")
    theory = Theory(predicate_definitions=[PredicateDefinition("Person", {"name": "str"})])
    theory.add(Term("Person", "Alice"))
    theory.sentence_groups.append(
        SentenceGroup(name="goals", group_type=SentenceGroupType.GOAL, sentences=[Term("Person", x)])
    )

    sql = SQLCompiler().compile(theory)

    assert fetchall(sql.removesuffix(";")) == [("Alice",)]


def test_theory_without_goal_compiles_relation_inspection_sql():
    """The compiler emits relation inspection SQL when no goal is available."""
    theory = Theory(predicate_definitions=[PredicateDefinition("Person", {"name": "str"})])
    theory.add(Term("Person", "Alice"))

    sql = SQLCompiler().compile(theory)

    assert fetchall(sql.removesuffix(";")) == [("Alice",)]
