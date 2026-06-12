from abc import ABC, abstractmethod
from collections import abc
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, ClassVar, Dict, Iterable, Iterator, List, Optional, Set, TextIO, Tuple, Type, Union

from typedlogic import FactMixin, Variable
from typedlogic.datamodel import (
    Exists,
    PredicateDefinition,
    Sentence,
    SentenceGroup,
    SentenceGroupType,
    Term,
    Theory,
    TermBag,
)
from typedlogic.parsers.pyparser.python_parser import PythonParser
from typedlogic.profiles import Profile, UnspecifiedProfile
from typedlogic.pybridge import fact_to_term

ELEMENT = Union[FactMixin, SentenceGroup, Sentence, Theory, PredicateDefinition]


@dataclass
class Solution:
    satisfiable: Optional[bool] = None


@dataclass
class Model:
    """
    A model is a set of ground terms that satisfy a set of axioms.
    """

    description: Optional[str] = None
    source_object: Optional[Any] = None
    ground_terms: List[Term] = field(default_factory=list)
    _predicate_index: Optional[Dict[str, List[Term]]] = field(default=None, init=False, repr=False, compare=False)
    _indexed_count: int = field(default=0, init=False, repr=False, compare=False)

    def retrieve(self, predicate: Union[str, type], *args) -> List[Term]:
        return list(self.iter_retrieve(predicate, *args))

    def _ensure_predicate_index(self) -> Dict[str, List[Term]]:
        # the index is rebuilt if ground_terms has grown or shrunk; in-place
        # replacement of a term at the same length is not detected
        if self._predicate_index is None or self._indexed_count != len(self.ground_terms):
            index: Dict[str, List[Term]] = {}
            for t in self.ground_terms:
                index.setdefault(t.predicate, []).append(t)
            self._predicate_index = index
            self._indexed_count = len(self.ground_terms)
        return self._predicate_index

    def iter_retrieve(self, predicate: Union[str, type], *args) -> Iterator[Term]:
        """
        Retrieve all ground terms with a given predicate.

        :param predicate:
        :return:
        """
        if isinstance(predicate, type):
            predicate = predicate.__name__
        for t in self._ensure_predicate_index().get(predicate, []):
            if args:
                t_values = t.values
                is_match = True
                for i, arg in enumerate(args):
                    if arg is not None and arg != t_values[i]:
                        is_match = False
                        break
                if not is_match:
                    continue
            yield t


@dataclass
class Method:
    """
    A method is a way to solve a set of axioms.
    """

    name: str
    description: Optional[str] = None
    is_default: bool = False
    impl_class: Optional[Type] = None


@dataclass
class Solver(ABC):
    """
    A solver an engine that can check a theory for consistency, satisfiability, or can infer new sentences.

    This is an abstract class that defines the *interface* for a solver.

    You can retrieve a specific solver with the `get_solver` function:

        >>> from typedlogic.registry import get_solver
        >>> solver = get_solver("clingo")

    Note that all solvers are provided via *integrations*, and may not be installed by default.
    Some may require additional command line setup.

    Once you have a solver, you can add theories, or individual sentences to it:

        >>> from typedlogic.integrations.frameworks.pydantic import FactBaseModel
        >>> class AncestorOf(FactBaseModel):
        ...     ancestor: str
        ...     descendant: str
        >>> solver.add_predicate_definition(PredicateDefinition(predicate="AncestorOf", arguments={'ancestor': str, 'descendant': str}))
        >>> from typedlogic import Term, Variable
        >>> x = Variable("x")
        >>> y = Variable("y")
        >>> z = Variable("z")
        >>> solver.add( (Term("AncestorOf", x, z) & Term("AncestorOf", z, y)) >> Term("AncestorOf", x, y))

    And facts:

        >>> solver.add_fact(AncestorOf(ancestor='p1', descendant='p1a'))
        >>> solver.add_fact(AncestorOf(ancestor='p1a', descendant='p1aa'))
        >>> aa = SentenceGroup(name="transitivity-of-ancestor-of")
        >>> solver.add_sentence_group(aa)

    The `check` method ensures the theory and ground terms (data) are consistent:

        >>> soln = solver.check()
        >>> soln.satisfiable
        True

    You can then query for models:

        >>> model = solver.model()
        >>> for t in model.ground_terms:
        ...     print(t)
        AncestorOf(p1, p1a)
        AncestorOf(p1a, p1aa)
        AncestorOf(p1, p1aa)

    """

    strict: bool = False
    method_name: Optional[str] = None
    methods_supported: ClassVar[Optional[List[Method]]] = None
    profile: ClassVar[Profile] = UnspecifiedProfile()
    assume_closed_world: bool = False

    # TODO: move towards this
    base_theory: Theory = field(default_factory=Theory)

    predicate_definitions: Optional[Dict[str, PredicateDefinition]] = None
    type_definitions: Dict[str, str] = field(default_factory=dict)
    constants: Dict[str, Any] = field(default_factory=dict)
    goals: Optional[List[SentenceGroup]] = None
    _sentences_added: Set[Sentence] = field(default_factory=set, init=False, repr=False, compare=False)
    _unhashable_sentences_added: List[Sentence] = field(default_factory=list, init=False, repr=False, compare=False)

    @property
    def method(self) -> Method:
        if self.methods_supported is None:
            raise NotImplementedError("Solver must define methods_supported")
        for m in self.methods_supported:
            if self.method_name is None and m.is_default:
                return m
            if m.name == self.method_name:
                return m
        raise ValueError(f"Method {self.method_name} not supported")

    @abstractmethod
    def check(self) -> Solution:
        pass

    def model(self) -> Model:
        return next(self.models())

    @abstractmethod
    def models(self) -> Iterator[Model]:
        pass

    def prove_goals(self, strict=True) -> Iterable[Tuple[Sentence, Optional[bool]]]:
        if not self.check().satisfiable:
            raise ValueError("Cannot prove goals for unsatisfiable theory")
        if not self.goals:
            raise ValueError("No goals to prove")
        for goal_group in self.goals:
            if not goal_group.sentences:
                raise ValueError(f"Goal group {goal_group.name} has no sentences")
            for sentence in goal_group.sentences:
                provable = self.prove(sentence)
                if not provable and strict:
                    raise ValueError(f"Goal {sentence} not provable")
                yield sentence, provable

    def prove_multiple(self, sentences: List[Sentence]) -> Iterable[Tuple[Sentence, Optional[bool]]]:
        if self.check().satisfiable is False:
            raise ValueError("Cannot prove goals for unsatisfiable theory")
        if not sentences:
            raise ValueError("No goals to prove")
        for sentence in sentences:
            provable = self.prove(sentence)
            yield sentence, provable

    def prove(self, sentence: Sentence) -> Optional[bool]:
        """
        Prove a sentence.

        :param sentence:
        :return:
        """
        if isinstance(sentence, Term):
            # Note: the default implementation may be highly ineffecient.
            # it is recommended to override this method in a subclass.
            sentence_values = sentence.values
            has_vars = any(isinstance(v, Variable) for v in sentence_values)
            model = self.model()
            for t in model.iter_retrieve(sentence.predicate):
                if t == sentence:
                    return True
                if has_vars:
                    t_values = t.values
                    is_match = True
                    for arg_val, t_val in zip(sentence_values, t_values, strict=False):
                        if isinstance(arg_val, Variable):
                            # auto-match (assume existential over whole domain)
                            continue
                        if arg_val != t_val:
                            is_match = False
                            break
                    if is_match:
                        return True
            return False
        if isinstance(sentence, Exists):
            inner = sentence.sentence
            if isinstance(inner, Term):
                return self.prove(inner)
        return None

    def load(self, source: Union[str, Path, TextIO, ModuleType]) -> None:
        """
        Load a theory from a file.

        :param source:
        :return:
        """
        parser = PythonParser()
        if isinstance(source, ModuleType):
            theory = parser.transform(source)
        else:
            theory = parser.parse(source)
        self.add(theory)

    def add(self, element: Union[ELEMENT, Iterable[ELEMENT]]) -> None:
        if isinstance(element, (list, abc.Iterator)):
            for e in element:
                self.add(e)
            return
        if isinstance(element, FactMixin):
            self.add_fact(element)
        elif isinstance(element, SentenceGroup):
            self.add_sentence_group(element)
        elif isinstance(element, Theory):
            self.add_theory(element)
        elif isinstance(element, PredicateDefinition):
            self.add_predicate_definition(element)
        elif isinstance(element, TermBag):
            for t in element.as_terms():
                self.add(t)
        elif isinstance(element, Sentence):
            self.add_sentence(element)
        else:
            raise ValueError(f"Unsupported axiom type: {type(element)}")

    def add_fact(self, fact: FactMixin):
        self.base_theory.ground_terms.append(fact_to_term(fact))

    def add_sentence_group(self, sentence_group: SentenceGroup) -> None:
        self.base_theory.sentence_groups.append(sentence_group)
        if sentence_group.group_type == SentenceGroupType.GOAL:
            if not self.goals:
                self.goals = []
            self.goals.append(sentence_group)
        if sentence_group.sentences:
            for sentence in sentence_group.sentences:
                self._register_sentence(sentence)
                self.add_sentence(sentence)

    def _register_sentence(self, sentence: Sentence) -> bool:
        """
        Record a sentence as part of the base theory, returning True if it was already registered.

        Sentences are tracked in a set; sentences embedding unhashable values
        (e.g. raw fact objects in probabilistic terms) fall back to a linear scan.
        """
        try:
            if sentence in self._sentences_added:
                return True
            self._sentences_added.add(sentence)
        except TypeError:
            if sentence in self._unhashable_sentences_added:
                return True
            self._unhashable_sentences_added.append(sentence)
        return False

    def add_sentence(self, sentence: Sentence) -> None:
        if self._register_sentence(sentence):
            return
        self.base_theory.sentence_groups.append(SentenceGroup(name="dynamic", sentences=[sentence]))

    def add_predicate_definition(self, predicate_definition: PredicateDefinition) -> None:
        """
        Add a predicate definition to the solver.

        Some solvers do not need predicate definitions (for example, classic prolog systems, as well
        as pure FOL solvers). However, many solvers need some kind of typing information.

        :param predicate_definition:
        :return:
        """
        self.base_theory.predicate_definitions.append(predicate_definition)

    def add_theory(self, theory: Theory) -> None:
        if theory.constants:
            for k, v in theory.constants.items():
                self.constants[k] = v
                self.base_theory.constants[k] = v
        if theory.type_definitions:
            for k, v in theory.type_definitions.items():
                self.type_definitions[k] = v
                self.base_theory.type_definitions[k] = v
        if theory.predicate_definitions:
            for p in theory.predicate_definitions:
                self.add_predicate_definition(p)
        if theory.sentence_groups:
            for aa in theory.sentence_groups:
                self.add_sentence_group(aa)
        if theory.ground_terms:
            for t in theory.ground_terms:
                self.add(t)

    def dump(self) -> str:
        """
        Dump the internal state of the solver as a string.

        :return:
        """
        raise NotImplementedError
