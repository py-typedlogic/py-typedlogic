import logging
import sqlite3
from dataclasses import dataclass, field
from typing import ClassVar, Dict, Iterator, List, Optional, Union

import snakelog.common as snakelog
import snakelog.litelog as litelog
from snakelog.common import Var
from snakelog.souffle import SouffleSolver

import typedlogic as tlog
import typedlogic.pybridge
from typedlogic import FactMixin
from typedlogic.datamodel import (
    NotInProfileError,
    PredicateDefinition,
    Sentence,
    Term,
)
from typedlogic.parsers.pyparser.python_ast_utils import logger
from typedlogic.profiles import (
    ClassicDatalog,
    ExcludedProfile,
    MixedProfile,
    Profile,
    PropositionalLogic,
    UnsortedLogic,
)
from typedlogic.pybridge import fact_arg_values, fact_predicate
from typedlogic.solver import Method, Model, Solution, Solver
from typedlogic.transformations import to_horn_rules

logger = logging.getLogger(__name__)

PRIMITIVE_TYPES = (int, float, str, bool, bytes)

@dataclass
class SnakeLogSolver(Solver):
    """
    A solver that uses snakelog.

    Snakelog is a lightweight Datalog engine that uses SQLite as a backend,
    for more details see [this blog post](https://www.philipzucker.com/snakelog-post/).

    While Snakelog is only supports a limited subset of Datalog, it has the advantage of being
    **fast** and requiring no additional dependencies. It is well suited for simple traversal-style
    logic programming problems, such as the one below.

        >>> from typedlogic.integrations.frameworks.pydantic import FactBaseModel
        >>> from typedlogic import Implies, And, Variable
        >>> class AncestorOf(FactBaseModel):
        ...     ancestor: str
        ...     descendant: str
        >>> class ParentOf(FactBaseModel):
        ...     parent: str
        ...     child: str
        >>> solver = SnakeLogSolver(strict=True)
         >>> from typedlogic import SentenceGroup, PredicateDefinition
        >>> solver.add_predicate_definition(PredicateDefinition(predicate="AncestorOf", arguments={'ancestor': str, 'descendant': str}))
        >>> solver.add_predicate_definition(PredicateDefinition(predicate="ParentOf", arguments={'parent': str, 'child': str}))
        >>> solver.add_fact(ParentOf(parent='p1', child='p1a'))
        >>> solver.add_fact(ParentOf(parent='p1a', child='p1aa'))
        >>> X = Variable("X")
        >>> Y = Variable("Y")
        >>> Z = Variable("Z")
        >>> solver.add_sentence(Implies(Term(ParentOf.__name__, X, Y), Term(AncestorOf.__name__, X, Y)))
        >>> solver.add_sentence(Implies(And(Term(AncestorOf.__name__, X, Z),
        ...                                 Term(AncestorOf.__name__, Z, Y)),
        ...                             Term(AncestorOf.__name__, X, Y)))
        >>> model = solver.model()
        >>> facts = [str(f) for f in model.ground_terms]
        >>> for f in sorted(facts):
        ...     print(f)
        AncestorOf(p1, p1a)
        AncestorOf(p1, p1aa)
        AncestorOf(p1a, p1aa)
        ParentOf(p1, p1a)
        ParentOf(p1a, p1aa)

    This solver does not implement the open-world assumption.

        >>> from typedlogic.profiles import OpenWorld
        >>> solver.profile.impl(OpenWorld)
        False
    """

    _wrapped_solver: Optional[snakelog.BaseSolver] = None
    predicate_map: Optional[Dict[str, PredicateDefinition]] = None
    sentences: List[Sentence] = field(default_factory=list)

    profile: ClassVar[Profile] = MixedProfile(ClassicDatalog(), UnsortedLogic(), ExcludedProfile(PropositionalLogic()))

    methods_supported: ClassVar[List[Method]] = [
        Method(name="litelog", impl_class=litelog.Solver, is_default=True),
        Method(name="souffle", impl_class=SouffleSolver),
    ]

    @property
    def wrapped_solver(self) -> snakelog.BaseSolver:
        if self._wrapped_solver is None:
            impl_class = self.method.impl_class
            if impl_class is None:
                raise ValueError("No implementation class defined")
            self._wrapped_solver = impl_class()
        return self._wrapped_solver

    def check(self) -> Solution:
        return Solution(satisfiable=None)

    def models(self) -> Iterator[Model]:
        s = self.wrapped_solver
        s.run()

        facts = []
        if not self.predicate_map:
            raise ValueError("Predicates have not been defined")
        for p, pd in self.predicate_map.items():
            tbl = self.to_predicate(p)
            try:
                res = s.con.execute(f"SELECT * FROM {tbl}")
                for fact in res.fetchall():
                    bindings = dict(zip(pd.arguments.keys(), fact[0:], strict=False))
                    fact = Term(p, bindings)
                    facts.append(fact)
            except sqlite3.OperationalError:
                # TODO: better way to detect zero implications
                pass
        m = Model(
            source_object=s,
            ground_terms=facts
        )
        yield m

    def prove(self, sentence: Sentence) -> Optional[bool]:
        return super().prove(sentence)

    def add_fact(self, fact: FactMixin) -> None:
        p = self.to_predicate(fact_predicate(fact))
        atom = litelog.Atom(p, list(fact_arg_values(fact)))
        self.wrapped_solver.add(atom)
        self.sentences.append(fact)

    def add_sentence(self, sentence: Sentence) -> None:
        try:
            for sentence in to_horn_rules(sentence):
                for snakelog_expr in self.to_clauses(sentence):
                    self.wrapped_solver.add(snakelog_expr)
                    self.sentences.append(sentence)
        except NotInProfileError as e:
            logger.info(f"SKIPPING: {sentence} // {e}")
            if self.strict:
                raise e

    def _string_type(self) -> str:
        # TODO: remove after the following is fixed
        # https://github.com/philzook58/snakelog/issues/4
        if self.method_name == "souffle":
            return "symbol"
        return "TEXT"

    def add_predicate_definition(self, predicate_definition: PredicateDefinition) -> None:
        if not self.predicate_map:
            self.predicate_map = {}
        s = self.wrapped_solver
        string_type = self._string_type()
        arg_types = [string_type for _ in predicate_definition.arguments.keys()]
        sig = [self.to_predicate(predicate_definition.predicate)] + arg_types
        s.Relation(*sig)
        self.predicate_map[predicate_definition.predicate] = predicate_definition

    def to_predicate(self, predicate: str) -> str:
        return predicate.lower()

    def to_clauses(self, sentence: Sentence) -> List[Union[litelog.Clause, litelog.Atom]]:
        if isinstance(sentence, tlog.Forall):
            return self.to_clauses(sentence.sentence)
        if isinstance(sentence, tlog.Implied):
            return self.to_clauses(tlog.Implies(sentence.operands[1], sentence.operands[0]))
        if isinstance(sentence, tlog.Iff):
            return self.to_clauses(tlog.And(tlog.Implies(sentence.left, sentence.right),
                                            tlog.Implies(sentence.right, sentence.left)))
        if isinstance(sentence, tlog.And):
            sentences = []
            for s in sentence.operands:
                sentences.extend(self.to_clauses(s))
            return sentences
        return [self.to_clause(sentence)]

    def to_clause(self, sentence: Sentence) -> Union[litelog.Clause, litelog.Atom]:
        if isinstance(sentence, tlog.Forall):
            return self.to_clause(sentence.sentence)
        if isinstance(sentence, tlog.Implies):
            head = self.to_atom(sentence.consequent)
            body = self.to_body(sentence.antecedent)
            return litelog.Clause(head, body)
        if isinstance(sentence, tlog.Term):
            # unit clause
            return self.to_atom(sentence)
        raise NotInProfileError(f"Unknown clause type {type(sentence)} :: {sentence}")

    def to_atom(self, sentence: Sentence) -> litelog.Atom:
        if isinstance(sentence, tlog.Term):
            def _render_arg(arg):
                if arg is None:
                    return None
                if isinstance(arg, tlog.Variable):
                    # TODO: this should be the norm after normalization
                    arg = arg.name
                    return Var(arg.upper())
                else:
                    if isinstance(arg, PRIMITIVE_TYPES):
                        return arg
                    else:
                        return str(arg)
            return litelog.Atom(self.to_predicate(sentence.predicate), [_render_arg(a) for a in sentence.bindings.values()])
        if isinstance(sentence, typedlogic.pybridge.FactMixin):
            def _render_arg(arg):
                if arg is None:
                    return None
                return Var(arg.upper())
            p = self.to_predicate(fact_predicate(sentence))
            return litelog.Atom(p, [_render_arg(a) for a in fact_arg_values(sentence)])
        raise NotInProfileError(f"Unknown atom type {type(sentence)} :: {sentence}")

    def to_body(self, sentence: Sentence) -> litelog.Body:
        if isinstance(sentence, tlog.And):
            atoms = [self.to_atom(s) for s in sentence.operands]
            return litelog.Body(atoms)
        if isinstance(sentence, (tlog.Term, typedlogic.pybridge.FactMixin)):
            return litelog.Body([self.to_atom(sentence)])
        raise NotInProfileError(f"Unknown body type {type(sentence)} :: {sentence}")



    def dump(self) -> str:
        return str(self.wrapped_solver)

