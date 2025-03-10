import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional, Set, Type, Union

from typedlogic import PredicateDefinition, Sentence, Theory
from typedlogic.integrations.frameworks.owldl import Thing, TopDataProperty, TopObjectProperty
from typedlogic.integrations.frameworks.owldl.owlpy_parser import OWLPyParser
from typedlogic.integrations.frameworks.owldl.owltop import Ontology
from typedlogic.integrations.solvers.clingo import ClingoSolver
from typedlogic.parsers.pyparser.introspection import introspect_attributes
from typedlogic.parsers.pyparser.python_parser import PythonParser, compile_python
from typedlogic.solver import Model, Solver
from typedlogic.utils.import_closure import compute_import_closure


def get_all_subclasses(cls: Type) -> Set[Type]:
    subclasses = set(cls.__subclasses__())
    return subclasses.union(s for c in subclasses for s in get_all_subclasses(c))


@dataclass
class OWLReasoner:
    """
    A reasoner for OWL-DL ontologies.

    The reasoner is initialized with a theory, which can be loaded from a file or built up programmatically.

    Let's start with a simple data model. Note our data model must be heavily *normalized* to be visible
    to OWL-DL. All individuals are represented as subclasses of Thing. These can't (yet) have properties
    of their own, these must be represented as separate relationships, which are subclasses of TopObjectProperty.

    Our model will have a class for representing people, and a relationship for representing who knows who.

        >>> class Person(Thing):
        ...     pass
        >>> class Knows(TopObjectProperty):
        ...     domain = Person
        ...     range = Person
        ...     symmetric = True

    We can now create an OWL reasoner:

        >>> from typedlogic.integrations.frameworks.owldl.reasoner import OWLReasoner
        >>> r = OWLReasoner()
        >>> r.init_axioms([Person, Knows])

    And add some facts. These are standard python objects:

        >>> r.add(Knows("p1", "p2"))

    We can now reason with the model:

        >>> assert r.coherent()
        >>> model = r.model()
        >>> for fact in model.iter_retrieve("Knows"):
        ...     print(fact)
        Knows(p1, p2)
        Knows(p2, p1)

    Note that because we declared the relationship as symmetric, the reasoner inferred the reverse relationship.

    By default, the reasoner uses the Clingo solver. This can be changed by setting the `solver_class` attribute.

        >>> from typedlogic.integrations.solvers.souffle import SouffleSolver
        >>> r = OWLReasoner(solver_class=SouffleSolver)
        >>> r.init_axioms([Person, Knows])
        >>> r.add(Knows("p1", "p2"))
        >>> assert r.coherent()
        >>> model = r.model()
        >>> for fact in model.iter_retrieve("Knows"):
        ...     print(fact)
        Knows(p1, p2)
        Knows(p2, p1)

    """

    solver_class: Type[Solver] = ClingoSolver
    theory: Optional[Theory] = None
    solver: Optional[Solver] = None

    def set_solver_class(self, solver_class: Type[Solver]):
        self.solver_class = solver_class
        self.solver = None

    def init_from_file(self, source: Union[str, Path]):
        p = OWLPyParser()
        self.theory = p.parse(source)

    def init_axioms(self, classes: Optional[List[Type]] = None):
        """
        Initializes axioms from what is currently loaded.
        :return:
        """
        import typedlogic.integrations.frameworks.owldl.owltop as owltop

        p = OWLPyParser()
        modules = None
        if classes:
            modules = []
            for cls in classes:
                module = inspect.getmodule(cls)
                if module:
                    modules.append(module)
            modules = list(set(modules))

        self.theory = p.parse(owltop.__file__, include_all=True, modules=modules)
        if classes:
            for cls in classes:
                pd = PredicateDefinition(cls.__name__, introspect_attributes(cls))
                self.theory.predicate_definitions.append(pd)

    def add(self, sentence: Union[Sentence, List[Sentence]]):
        """
        Add a sentence to the reasoner

        :param sentence:
        :return:
        """
        self.solver = None  # solver's state is invalidated
        if isinstance(sentence, list):
            for s in sentence:
                if s is None:
                    raise ValueError(f"Got empty sentence in {sentence}")
                self.add(s)
            return
        if self.theory is None:
            self.theory = Theory()
        self.theory.add(sentence)

    def register(self, cls: Type):
        """
        Register a python class with the reasoner

        :param cls:
        :return:
        """
        if not self.theory:
            self.theory = Theory()
        pd_map = {pd.predicate: pd for pd in self.theory.predicate_definitions or []}
        pd = None
        for mc in [Thing, TopObjectProperty, TopDataProperty]:
            if issubclass(cls, mc):
                pd = PredicateDefinition(cls.__name__, pd_map[mc.__name__].arguments)
        if not pd:
            raise ValueError(f"Class {cls} is not a recognized OWL-DL class")
        self.theory.predicate_definitions.append(pd)
        sentences = cls.to_sentences()
        for s in sentences:
            self.add(s)

    def remove(self, sentence: Union[Sentence, List[Sentence]]):
        self.solver = None  # solver's state is invalidated
        if isinstance(sentence, list):
            for s in sentence:
                self.remove(s)
            return
        if self.theory is None:
            raise ValueError("No theory to remove from")
        self.theory.remove(sentence)

    def reason(self) -> None:
        self.solver = self.solver_class()
        if not self.theory:
            raise ValueError("No theory to reason with")
        self.solver.add_theory(self.theory)

    def model(self) -> Model:
        if not self.solver:
            self.reason()
        if not self.solver:
            raise ValueError("No solver to reason with")
        solver = self.solver
        return solver.model()

    def model_iter(self) -> Iterator[Model]:
        if not self.solver:
            self.reason()
        if not self.solver:
            raise ValueError("No solver to reason with")
        solver = self.solver
        yield from solver.models()

    def coherent(self) -> bool:
        if not self.solver:
            self.reason()
        if not self.solver:
            raise ValueError("No solver to reason with")
        solver = self.solver
        return solver.check().satisfiable is not False
