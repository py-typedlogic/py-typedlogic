"""
A solver that computes the *well-founded model* of a normal logic program.

The well-founded semantics (WFS) assigns every ground atom one of three truth
values -- ``true``, ``false``, or ``undefined`` -- and always yields exactly one
model, computable in polynomial time. It is the three-valued, skeptical
counterpart to the (two-valued, credulous, possibly-multiple) stable-model
semantics implemented by :class:`~typedlogic.integrations.solvers.clingo.ClingoSolver`.

Three interchangeable **backends** are provided, selected with the ``backend``
field:

``native`` (default)
    A dependency-free pure-Python implementation of the Van Gelder *alternating
    fixpoint*. It grounds the program over its Herbrand universe and returns the
    full three-valued model (``true`` / ``false`` / ``undefined``). This is the
    reference backend used in the documentation. It is intended for teaching and
    modestly-sized programs: grounding is by naive instantiation, so it is not a
    substitute for an industrial grounder on large or deeply-recursive programs
    (use the ``xsb`` backend for those).

``problog``
    Delegates to `ProbLog <https://dtai.cs.kuleuven.be/problog/>`_, a mature
    engine already integrated with typedlogic. ProbLog evaluates the *two-valued*
    restriction of WFS: it agrees with the native backend on programs whose
    well-founded model is total (e.g. stratified programs) and raises
    :class:`NegativeCycleError` on programs whose well-founded model is genuinely
    three-valued. It therefore never reports ``undefined`` -- it refuses instead.

``xsb`` (experimental, unverified)
    Drives `XSB Prolog <https://xsb.sourceforge.net/>`_, the reference SLG /
    tabling engine for the well-founded semantics, as an external subprocess --
    the backend to reach for on large or recursive programs. Like the other
    external-binary integrations (Souffle, Prover9) it requires the ``xsb``
    executable on ``PATH``; when it is absent a clear error is raised.

    .. warning::
       This backend is **experimental and has not been executed against a live
       XSB install** -- it is written to XSB's documented ``call_tv/2`` API but
       is not exercised in CI (the tests skip when ``xsb`` is not on ``PATH``).
       It emits a :class:`UserWarning` when used. Prefer the ``native`` backend
       until the ``xsb`` path has been validated against real XSB output.
"""

import logging
import shutil
import subprocess
import tempfile
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Dict, FrozenSet, Iterator, List, Set, Tuple

from typedlogic import And, Forall, Implies, Term, Variable
from typedlogic.datamodel import NegationAsFailure, NotInProfileError, Sentence
from typedlogic.profiles import MixedProfile, Profile, SingleModelSemantics, WellFoundedSemantics
from typedlogic.solver import Model, Solution, Solver
from typedlogic.transformations import PrologConfig, as_prolog

logger = logging.getLogger(__name__)

# A ground atom is a predicate name plus a tuple of constant argument values.
GroundAtom = Tuple[str, Tuple]


class NegativeCycleError(NotInProfileError):
    """
    Raised by two-valued backends when the well-founded model is not total.

    Backends such as ``problog`` only support programs whose well-founded model
    assigns every atom ``true`` or ``false``. A negative recursive cycle (e.g.
    ``p :- not q. q :- not p.``) makes atoms *undefined*, which these backends
    cannot represent; use the ``native`` (or ``xsb``) backend for such programs.
    """


@dataclass
class GroundRule:
    """A ground (variable-free) rule ``head :- pos, not naf``."""

    head: GroundAtom
    pos: FrozenSet[GroundAtom]
    naf: FrozenSet[GroundAtom]


@dataclass
class WellFoundedModel(Model):
    """
    A three-valued model.

    :attr:`ground_terms` holds the atoms that are **true** in the well-founded
    model (mirroring the two-valued :class:`~typedlogic.solver.Model` contract, so
    ``iter_retrieve`` and friends behave as usual). The atoms that are neither
    true nor false -- i.e. paradoxical or mutually-dependent under negation -- are
    exposed separately via :attr:`undefined_terms`. Atoms in neither list are
    false.
    """

    undefined_terms: List[Term] = field(default_factory=list)


@dataclass
class WellFoundedSolver(Solver):
    """
    A solver that computes the well-founded model of a normal logic program.

        >>> from typedlogic import NegationAsFailure, PredicateDefinition, Variable
        >>> from typedlogic.integrations.solvers.wellfounded import WellFoundedSolver
        >>> solver = WellFoundedSolver()
        >>> solver.add_predicate_definition(PredicateDefinition(predicate="Bird", arguments={'name': 'str'}))
        >>> solver.add_predicate_definition(PredicateDefinition(predicate="Abnormal", arguments={'name': 'str'}))
        >>> solver.add_predicate_definition(PredicateDefinition(predicate="Flies", arguments={'name': 'str'}))

    A bird flies unless it can be shown abnormal (negation as failure, expressed
    programmatically with :class:`~typedlogic.datamodel.NegationAsFailure`):

        >>> x = Variable("x")
        >>> solver.add((Term("Bird", x) & NegationAsFailure(Term("Abnormal", x))) >> Term("Flies", x))
        >>> solver.add(Term("Bird", "tweety"))
        >>> model = solver.model()
        >>> [str(t) for t in model.iter_retrieve("Flies")]
        ['Flies(tweety)']

    This solver implements the closed-world assumption but not the open-world one:

        >>> from typedlogic.profiles import OpenWorld, ClosedWorld
        >>> solver.profile.impl(ClosedWorld)
        True
        >>> solver.profile.impl(OpenWorld)
        False

    Unlike ASP, an ambiguous negative loop does not produce multiple models (or
    none); the offending atoms become *undefined*:

        >>> solver = WellFoundedSolver()
        >>> solver.add_predicate_definition(PredicateDefinition(predicate="p", arguments={}))
        >>> solver.add_predicate_definition(PredicateDefinition(predicate="q", arguments={}))
        >>> solver.add(NegationAsFailure(Term("q")) >> Term("p"))
        >>> solver.add(NegationAsFailure(Term("p")) >> Term("q"))
        >>> model = solver.model()
        >>> model.ground_terms
        []
        >>> sorted(str(t) for t in model.undefined_terms)
        ['p', 'q']

    """

    backend: str = field(default="native")
    exec_name: str = field(default="xsb")
    profile: ClassVar[Profile] = MixedProfile(WellFoundedSemantics(), SingleModelSemantics())

    def check(self) -> Solution:
        """Report satisfiability; a well-founded model always exists, so this is always true."""
        self.model()
        return Solution(satisfiable=True)

    def models(self) -> Iterator[Model]:
        """Yield the single well-founded model."""
        yield self.model()

    def model(self) -> WellFoundedModel:
        """Return the single well-founded model (with three-valued information)."""
        if self.backend == "native":
            return self._native_model()
        if self.backend == "problog":
            return self._problog_model()
        if self.backend == "xsb":
            return self._xsb_model()
        raise ValueError(f"Unknown WellFoundedSolver backend: {self.backend!r} (expected native, problog, or xsb)")

    # -- grounding (shared by the native and problog backends) -------------

    def _sentences(self) -> List[Sentence]:
        return list(self.base_theory.sentences) + list(self.base_theory.ground_terms)

    def _ground_rules(self) -> Tuple[List[GroundRule], Dict[GroundAtom, Term]]:
        """Ground every rule/fact, returning ground rules and an atom->Term map."""
        parsed: List[Tuple[Term, List[Term], List[Term]]] = []
        constants: Set = set()
        for sentence in self._sentences():
            head, pos, naf = self._destructure(sentence)
            for t in [head, *pos, *naf]:
                constants.update(v for v in t.values if not isinstance(v, Variable))
            parsed.append((head, pos, naf))

        universe = sorted(constants, key=str)
        ground_rules: List[GroundRule] = []
        atom_terms: Dict[GroundAtom, Term] = {}

        def register(term: Term) -> GroundAtom:
            atom = (term.predicate, tuple(term.values))
            atom_terms.setdefault(atom, term)
            return atom

        for head, pos, naf in parsed:
            variables = self._variables([head, *pos, *naf])
            for binding in self._bindings(variables, universe):
                g_head = register(self._substitute(head, binding))
                g_pos = frozenset(register(self._substitute(t, binding)) for t in pos)
                g_naf = frozenset(register(self._substitute(t, binding)) for t in naf)
                ground_rules.append(GroundRule(g_head, g_pos, g_naf))
        return ground_rules, atom_terms

    def _destructure(self, sentence: Sentence) -> Tuple[Term, List[Term], List[Term]]:
        """Split a sentence into (head, positive body atoms, NAF body atoms)."""
        while isinstance(sentence, Forall):
            sentence = sentence.sentence
        if isinstance(sentence, Term):
            return sentence, [], []  # a fact
        if isinstance(sentence, Implies):
            head = sentence.consequent
            if not isinstance(head, Term):
                raise NotInProfileError(
                    f"WellFoundedSolver only supports rules with a single positive head atom, got: {head}"
                )
            body = sentence.antecedent
            literals = list(body.operands) if isinstance(body, And) else [body]
            pos: List[Term] = []
            naf: List[Term] = []
            for lit in literals:
                if isinstance(lit, NegationAsFailure):
                    inner = lit.operands[0]
                    if not isinstance(inner, Term):
                        raise NotInProfileError(f"NAF body literals must be atoms, got: {inner}")
                    naf.append(inner)
                elif isinstance(lit, Term):
                    pos.append(lit)
                else:
                    raise NotInProfileError(
                        "WellFoundedSolver body literals must be atoms or negation-as-failure atoms "
                        f"(use '-' for NAF); got: {type(lit).__name__} {lit}"
                    )
            return head, pos, naf
        raise NotInProfileError(f"WellFoundedSolver cannot interpret sentence: {type(sentence).__name__} {sentence}")

    @staticmethod
    def _variables(terms: List[Term]) -> List[str]:
        seen: List[str] = []
        for t in terms:
            for v in t.values:
                if isinstance(v, Variable) and v.name not in seen:
                    seen.append(v.name)
        return seen

    @staticmethod
    def _bindings(variables: List[str], universe: List) -> Iterator[Dict[str, object]]:
        if not variables:
            yield {}
            return
        if not universe:
            return  # a rule with variables but no constants grounds to nothing
        indices = [0] * len(variables)
        n = len(universe)
        while True:
            yield {var: universe[indices[i]] for i, var in enumerate(variables)}
            pos = len(variables) - 1
            while pos >= 0:
                indices[pos] += 1
                if indices[pos] < n:
                    break
                indices[pos] = 0
                pos -= 1
            if pos < 0:
                return

    @staticmethod
    def _substitute(term: Term, binding: Dict[str, object]) -> Term:
        if not binding:
            return term
        new_values = [binding.get(v.name, v) if isinstance(v, Variable) else v for v in term.values]
        return Term(term.predicate, *new_values)

    # -- native backend: the alternating fixpoint --------------------------

    @staticmethod
    def _gamma(rules: List[GroundRule], interpretation: Set[GroundAtom]) -> Set[GroundAtom]:
        """
        Least model of the Gelfond-Lifschitz reduct w.r.t. ``interpretation``.

        ``not a`` holds iff ``a`` is not in the (assumed-true) interpretation, so a
        rule survives the reduct iff none of its NAF atoms are in the interpretation.
        The reduct is a definite program, so its least model is found by forward
        chaining over the positive bodies.
        """
        reduct = [(r.head, r.pos) for r in rules if r.naf.isdisjoint(interpretation)]
        derived: Set[GroundAtom] = set()
        changed = True
        while changed:
            changed = False
            for head, pos in reduct:
                if head not in derived and pos <= derived:
                    derived.add(head)
                    changed = True
        return derived

    def _alternating_fixpoint(self, rules: List[GroundRule], start: Set[GroundAtom]) -> Set[GroundAtom]:
        # gamma is antimonotone, so gamma-squared is monotone; iterate to a fixpoint.
        current = set(start)
        while True:
            nxt = self._gamma(rules, self._gamma(rules, current))
            if nxt == current:
                return current
            current = nxt

    def _native_model(self) -> WellFoundedModel:
        rules, atom_terms = self._ground_rules()
        heads = {r.head for r in rules}
        true_atoms = self._alternating_fixpoint(rules, set())  # least fixpoint: definitely true
        non_false = self._alternating_fixpoint(rules, set(heads))  # greatest fixpoint: possibly true
        undefined_atoms = non_false - true_atoms
        return WellFoundedModel(
            ground_terms=[atom_terms[a] for a in true_atoms],
            undefined_terms=[atom_terms[a] for a in undefined_atoms],
        )

    # -- problog backend: two-valued WFS via a wrapped engine --------------

    def _problog_model(self) -> WellFoundedModel:
        try:
            from problog import get_evaluatable
            from problog.program import PrologString

            try:
                from problog.eval_nodes import NegativeCycle
            except ImportError:  # pragma: no cover - problog version dependent
                from problog.engine_stack import NegativeCycle
        except ImportError as e:  # pragma: no cover - exercised only without problog
            raise ImportError("The 'problog' backend requires problog: pip install 'typedlogic[problog]'") from e

        rules, atom_terms = self._ground_rules()
        program = self._prolog_program(query_atoms=atom_terms.values())
        try:
            result = get_evaluatable().create_from(PrologString(program)).evaluate()
        except NegativeCycle as e:
            # ProbLog raises on negative cycles: the two-valued WFS is undefined here.
            raise NegativeCycleError(
                "The 'problog' backend only supports programs with a total (two-valued) well-founded model; "
                f"this program is genuinely three-valued. Use backend='native' or 'xsb'. ProbLog reported: {e}"
            ) from e

        true_terms = []
        for term, prob in result.items():
            if prob and prob > 0.0:
                true_terms.append(self._atom_text_to_term(str(term), atom_terms))
        return WellFoundedModel(ground_terms=[t for t in true_terms if t is not None])

    # -- xsb backend: the reference WFS engine as an external subprocess ----

    def _xsb_model(self) -> WellFoundedModel:
        warnings.warn(
            "The 'xsb' WellFoundedSolver backend is experimental and has not been validated "
            "against a live XSB install; verify its output or use backend='native'.",
            UserWarning,
            stacklevel=2,
        )
        exe = shutil.which(self.exec_name)
        if exe is None:  # pragma: no cover - environment dependent
            raise FileNotFoundError(
                f"The 'xsb' backend requires the XSB Prolog executable {self.exec_name!r} on PATH. "
                "Install XSB from https://xsb.sourceforge.net/ or use backend='native'."
            )
        rules, atom_terms = self._ground_rules()
        candidates = list(atom_terms.values())
        program = self._prolog_program(query_atoms=None)
        # XSB's call_tv/2 returns the well-founded truth value (true / undefined);
        # atoms that fail outright are false. We print "<index> <tv>" per candidate.
        goals = []
        for i, term in enumerate(candidates):
            atom = as_prolog(term, self._prolog_config())
            goals.append(f"( call_tv(({atom}), TV{i}) -> writeln('WF {i} '(TV{i})) ; true )")
        driver = "main :- " + ", ".join(goals) + ", halt.\n" if goals else "main :- halt.\n"
        with tempfile.TemporaryDirectory() as d:
            prog_path = Path(d) / "program.P"
            prog_path.write_text(program + "\n" + driver, encoding="utf-8")
            res = subprocess.run(  # noqa: S603
                [exe, "--nobanner", "--quietload", "-e", f"consult('{prog_path}'), main."],
                capture_output=True,
                text=True,
            )
        true_terms: List[Term] = []
        undefined_terms: List[Term] = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line.startswith("WF "):
                continue
            _, idx, tv = line.split(" ", 2)
            term = candidates[int(idx)]
            if tv.startswith("undefined"):
                undefined_terms.append(term)
            else:
                true_terms.append(term)
        return WellFoundedModel(ground_terms=true_terms, undefined_terms=undefined_terms)

    # -- prolog rendering helpers (problog / xsb) --------------------------

    def _prolog_config(self) -> PrologConfig:
        return PrologConfig(negation_as_failure_symbol=r"\+", negation_symbol=r"\+", double_quote_strings=False)

    def _prolog_program(self, query_atoms) -> str:
        config = self._prolog_config()
        # as_prolog emits a trailing '.' for rules but not for bare atoms; normalize.
        lines = [self._terminate(as_prolog(s, config)) for s in self._sentences()]
        if query_atoms is not None:
            for term in query_atoms:
                lines.append(f"query({as_prolog(term, config)}).")
        return "\n".join(lines)

    @staticmethod
    def _terminate(clause: str) -> str:
        clause = clause.rstrip()
        return clause if clause.endswith(".") else clause + "."

    def _atom_text_to_term(self, text: str, atom_terms: Dict[GroundAtom, Term]):
        config = self._prolog_config()
        for term in atom_terms.values():
            if as_prolog(term, config) == text:
                return term
        return None
