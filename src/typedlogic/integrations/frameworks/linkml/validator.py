"""Validation helpers for direct LinkML ABox facts."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Optional, Type

from typedlogic import Term
from typedlogic.integrations.frameworks.linkml.reasoning import compile_schema_to_abox
from typedlogic.solver import Solver


def validate(schema: dict, facts: Iterable[Term], solver_class: Optional[Type[Solver]] = None) -> bool:
    """
    Validate ABox facts against a LinkML schema.

    The facts are expected to use the direct compile-away convention:
    class/type predicates are unary and slot predicates are binary, for example
    ``Person("p1")`` and ``name("p1", "n1")``.
    """
    theory = compile_schema_to_abox(schema)
    theory.ground_terms.extend(facts)
    if solver_class is None:
        from typedlogic.integrations.solvers.clingo.clingo_solver import ClingoSolver

        solver_class = ClingoSolver
    solver = solver_class()
    solver.add(theory)
    return bool(solver.check().satisfiable)
