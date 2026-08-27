"""
Run the metatheory over a theory and report what it derives.

Checking a theory here means solving a logic program: the theory is reflected into
ground facts, the axioms of :mod:`typedlogic.theories.metatheory.axioms` are loaded
alongside them, and any diagnostic predicate present in the resulting model is reported.

Because the check *is* a solve, adding a rule adds a check. A project that loads its own
`@axiom` module over the same vocabulary gets its rules enforced with no change here.
"""

from dataclasses import dataclass, field
from types import ModuleType
from typing import Any, List, Optional, Sequence, Union

from typedlogic import Term, Theory
from typedlogic.registry import get_solver
from typedlogic.solver import Solver
from typedlogic.theories.metatheory import axioms as metatheory_axioms
from typedlogic.theories.metatheory.reflection import skipped_sentences, theory_to_facts
from typedlogic.theories.metatheory.vocabulary import (
    ConstantClash,
    TypeClash,
    UndeclaredPredicate,
    UnstratifiedNegation,
)

#: The default solver: the metatheory uses stratified negation, which Clingo supports and
#: which open-world provers do not interpret the same way.
DEFAULT_SOLVER = "clingo"


@dataclass
class Diagnostic:
    """
    One finding derived by the metatheory.

    :ivar kind: The diagnostic predicate that produced this finding
    :ivar message: A human-readable rendering
    :ivar rule: The rule the finding is attributed to, where it has one
    :ivar term: The derived term, for callers that want the raw bindings
    """

    kind: str
    message: str
    rule: Optional[str] = None
    term: Optional[Term] = None

    def __str__(self) -> str:
        location = f"{self.rule}: " if self.rule else ""
        return f"{location}{self.message}"


@dataclass
class CheckResult:
    """
    The outcome of checking a theory.

    :ivar diagnostics: Everything the metatheory derived
    :ivar skipped: Asserted sentences that reflection could not describe
    """

    diagnostics: List[Diagnostic] = field(default_factory=list)
    skipped: List[Any] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """
        Report whether the check found nothing.

        A True result is bounded by :attr:`skipped`: sentences reflection could not
        describe contributed no facts and so could not produce a diagnostic.

        :return: True if no diagnostics were derived
        """
        return not self.diagnostics

    def __str__(self) -> str:
        if not self.diagnostics:
            return "no diagnostics"
        return "\n".join(str(d) for d in self.diagnostics)


def _render(kind: str, values: Sequence[Any]) -> Diagnostic:
    """
    Render a derived term as a diagnostic.

    :param kind: The diagnostic predicate name
    :param values: The term's argument values, in declaration order
    :return: The rendered diagnostic
    """
    if kind == TypeClash.__name__:
        rule, var, left, right = values
        return Diagnostic(
            kind,
            f"variable '{var}' is used at positions declared '{left}' and '{right}', which are not compatible",
            rule=str(rule),
        )
    if kind == ConstantClash.__name__:
        rule, predicate, position, declared, actual = values
        return Diagnostic(
            kind,
            f"a '{actual}' literal fills {predicate} argument {position}, which is declared '{declared}'",
            rule=str(rule),
        )
    if kind == UndeclaredPredicate.__name__:
        rule, predicate = values
        return Diagnostic(kind, f"predicate '{predicate}' is used but never declared", rule=str(rule))
    if kind == UnstratifiedNegation.__name__:
        (predicate,) = values
        return Diagnostic(kind, f"predicate '{predicate}' recurses through a negation")
    return Diagnostic(kind, f"{kind}{tuple(values)}")


#: Predicates reported as diagnostics. Extend this to surface a rule of your own.
DIAGNOSTIC_PREDICATES = (TypeClash, ConstantClash, UndeclaredPredicate, UnstratifiedNegation)


def _diagnostic_key(kind: str, values: Sequence[Any]) -> tuple:
    """
    Build the identity of a finding, for suppressing restatements of the same problem.

    Incompatibility is symmetric, so a clash is derived once in each direction; both
    describe one problem and should be reported once.

    :param kind: The diagnostic predicate name
    :param values: The term's argument values
    :return: A hashable key identifying the underlying finding
    """
    if kind == TypeClash.__name__:
        rule, var, left, right = values
        return (kind, rule, var, frozenset((left, right)))
    return (kind, tuple(values))


def check_theory(
    theory: Theory,
    solver: Optional[Union[str, Solver]] = None,
    extra_axioms: Optional[Sequence[ModuleType]] = None,
    extra_diagnostics: Optional[Sequence[type]] = None,
) -> CheckResult:
    """
    Check a theory by solving the metatheory over it.

        >>> from typedlogic import Theory
        >>> from typedlogic.datamodel import PredicateDefinition
        >>> theory = Theory(
        ...     name="ok",
        ...     predicate_definitions=[PredicateDefinition("Person", {"name": "str"})],
        ... )
        >>> check_theory(theory).ok
        True

    :param theory: The theory to check
    :param solver: A solver instance or registered name; defaults to Clingo, which is an
        optional dependency (``pip install "typedlogic[clingo]"``)
    :param extra_axioms: Further axiom modules over the metatheory vocabulary
    :param extra_diagnostics: Further predicates to report, for rules from `extra_axioms`
    :return: The diagnostics derived, together with what reflection skipped
    """
    if solver is None:
        solver = DEFAULT_SOLVER
    if isinstance(solver, str):
        solver = get_solver(solver)

    solver.load(metatheory_axioms)
    for module in extra_axioms or []:
        solver.load(module)
    for fact in theory_to_facts(theory):
        solver.add(fact)

    model = solver.model()
    diagnostics = []
    seen = set()
    for predicate in (*DIAGNOSTIC_PREDICATES, *(extra_diagnostics or [])):
        for term in model.retrieve(predicate):
            key = _diagnostic_key(predicate.__name__, term.values)
            if key in seen:
                continue
            seen.add(key)
            diagnostics.append(_render(predicate.__name__, term.values))
    return CheckResult(diagnostics=diagnostics, skipped=skipped_sentences(theory))
