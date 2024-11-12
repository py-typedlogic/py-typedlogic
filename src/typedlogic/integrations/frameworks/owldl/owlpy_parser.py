import inspect
from pathlib import Path
from types import ModuleType
from typing import Union, TextIO, Type, Set, Optional, List, Tuple

from typedlogic import Theory
from typedlogic.integrations.frameworks.owldl import Thing, TopDataProperty, TopObjectProperty, Ontology
from typedlogic.integrations.frameworks.owldl.owltop import Axiom
from typedlogic.parser import Parser
from typedlogic.parsers.pyparser import PythonParser
from typedlogic.parsers.pyparser.introspection import get_module_predicate_definitions
from typedlogic.parsers.pyparser.python_parser import compile_python
from typedlogic.utils.import_closure import compute_import_closure


def _get_all_subclasses(cls: Type) -> Set[Type]:
    subclasses = set(cls.__subclasses__())
    return subclasses.union(s for c in subclasses for s in _get_all_subclasses(c))


class OWLPyParser(Parser):
    """
    A parser that converts OWL programs in Python.

    OWLPy programs are programs that can mix standard typedlogic programs with syntactic sugar
    for OWL expressions. See the OWL-DL docs for more details.

    Example:

        >>> from typedlogic.transformations import as_fol
        >>> import tests.test_frameworks.owldl.family as family
        >>> parser = OWLPyParser()
        >>> theory = parser.parse_file(family.__file__)
        >>> pd = theory.predicate_definition_map["HasChild"]
        >>> pd.arguments
         {'subject': 'str', 'object': 'str'}
        >>> fol_strings = sorted([as_fol(s) for s in theory.sentences])
        >>> for s in fol_strings:
        ...     print(s)
        ∀[I J K]. HasChild(I, J) ∧ HasChild(J, K) → HasChild(I, K)
        ∀[I J K]. HasDescendant(I, J) ∧ HasDescendant(J, K) → HasDescendant(I, K)
        ∀[I J K]. HasGrandchild(I, J) ∧ HasGrandchild(J, K) → HasGrandchild(I, K)
        ∀[I J]. HasAncestor(I, J) ↔ HasDescendant(J, I)
        ∀[I J]. HasChild(I, J) → Person(I)
        ∀[I J]. HasChild(I, J) → Person(J)
        ∀[I J]. HasChild(I, J) → ¬HasChild(J, I)
        ∀[I J]. HasDescendant(I, J) → Person(I)
        ∀[I J]. HasDescendant(I, J) → Person(J)
        ∀[I J]. HasDescendant(I, J) → ¬HasDescendant(J, I)
        ∀[I J]. HasGrandchild(I, J) → Person(I)
        ∀[I J]. HasGrandchild(I, J) → Person(J)
        ∀[I J]. HasGrandchild(I, J) → ¬HasGrandchild(J, I)
        ∀[I J]. HasParent(I, J) ↔ HasChild(J, I)
        ∀[I]. Father(I) → Person(I)
        ∀[I]. Father(I) ↔ (Man(I) ∨ Woman(I)) ∧ ¬∃[I]. (¬Man(I) ∧ Woman(I))
        ∀[I]. Father(I) ↔ Parent(I) ∧ Man(I)
        ∀[I]. Man(I) → Person(I)
        ∀[I]. Man(I) ↔ (Man(I) ∨ Woman(I)) ∧ ¬∃[I]. (¬Man(I) ∧ Woman(I))
        ∀[I]. Parent(I) → Person(I)
        ∀[I]. Parent(I) ↔ (Man(I) ∨ Woman(I)) ∧ ¬∃[I]. (¬Man(I) ∧ Woman(I))
        ∀[I]. Parent(I) ↔ Person(I) ∧ ∃[J]. HasChild(I, J) ∧ Thing(J)
        ∀[I]. Person(I) → Thing(I)
        ∀[I]. Person(I) ↔ (Man(I) ∨ Woman(I)) ∧ ¬∃[I]. (¬Man(I) ∧ Woman(I))
        ∀[I]. Woman(I) → Person(I)
        ∀[I]. Woman(I) ↔ (Man(I) ∨ Woman(I)) ∧ ¬∃[I]. (¬Man(I) ∧ Woman(I))
        ∀[J0 J1 J2]. HasChild(J0, J1) ∧ HasChild(J1, J2) → HasGrandchild(J0, J2)
        ∀[P I J]. HasAncestor(I, J) → TopObjectProperty(I, J)
        ∀[P I J]. HasChild(I, J) → HasDescendant(I, J)
        ∀[P I J]. HasDescendant(I, J) → TopObjectProperty(I, J)
        ∀[P I J]. HasGrandchild(I, J) → HasDescendant(I, J)
        ∀[P I J]. HasParent(I, J) → HasAncestor(I, J)

    """

    def parse(
        self, source: Union[Path, str, TextIO], include_all=False, modules: Optional[List[ModuleType]] = None, **kwargs
    ) -> Theory:
        """
        Parse the source into a theory.

        :param source:
        :param include_all:
        :param modules:
        :param kwargs:
        :return:
        """
        theory, _ = self._parse_to_theory_and_axioms(source, include_all=include_all, modules=modules, **kwargs)
        return theory

    def parse_to_owl_axioms(
        self, source: Union[Path, str, TextIO], include_all=False, modules: Optional[List[ModuleType]] = None, **kwargs
    ) -> List[Axiom]:
        """
        Parse the source into a list of tl-OWL axioms.

        :param source:
        :param include_all:
        :param modules:
        :param kwargs:
        :return:
        """
        _, axioms = self._parse_to_theory_and_axioms(source, include_all=include_all, modules=modules, **kwargs)
        return axioms

    def _parse_to_theory_and_axioms(
        self, source: Union[Path, str, TextIO], include_all=False, modules: Optional[List[ModuleType]] = None, **kwargs
    ) -> Tuple[Theory, List[Axiom]]:
        p = PythonParser()

        def get_file():
            if isinstance(source, (Path, str)):
                return open(source)
            else:
                return source

        theory = p.parse(get_file())
        python_txt = get_file().read()
        # TODO: check for multiple invocations
        module = compile_python(python_txt, name=None, package_path=str(source))
        # module = importlib.import_module(str(source))
        theory.source_module_name = module.__name__
        # TODO: ensure loaded
        owl_axioms = self._generate_from_classes(theory, include_all=include_all, modules=modules)
        return theory, owl_axioms

    def _generate_from_classes(
        self, theory: Theory, include_all=False, modules: Optional[List[ModuleType]] = None
    ) -> List[Axiom]:
        """
        Iterates through owlpy classes, gathering axioms, and injecting corresponding FOL into the theory.

        :param theory:
        :param include_all:
        :param modules:
        :return:
        """
        owl_axioms = []
        class_classes = _get_all_subclasses(Thing)
        op_classes = _get_all_subclasses(TopObjectProperty)
        dp_classes = _get_all_subclasses(TopDataProperty)
        ont_classes = _get_all_subclasses(Ontology)
        all_classes = class_classes.union(op_classes).union(dp_classes).union(ont_classes)
        if modules:
            all_classes = {c for c in all_classes if inspect.getmodule(c) in modules}
        else:
            source_module_name = theory.source_module_name
            if source_module_name and not include_all:
                import_closure = compute_import_closure(source_module_name)
                all_classes = {c for c in all_classes if c.__module__ in import_closure}
        for cls in all_classes:
            sentences = []
            for a in cls.axioms():
                if a is not None:
                    s = a.as_fol()
                    s.add_annotation("owl_axiom", a)
                    if s not in sentences:
                        theory.add(s)
                    sentences.append(s)
            # sentences = cls.to_sentences()
            # for s in sentences:
            #    theory.add(s)
            # owl_axioms.extend(cls.axioms())
            # for root in [Thing, TopDataProperty, TopObjectProperty]:
            #    if issubclass(cls, root):
            #        pd =

        # print(f"|S|= {len(theory.sentences)}")

        for cls in all_classes:
            # Get the module where the class is defined
            module = inspect.getmodule(cls)

            if module:
                module_name = module.__name__

                # Check if __axioms__ is defined in the module
                if hasattr(module, "__axioms__"):
                    axioms = module.__axioms__
                    if not isinstance(axioms, list):
                        axioms = [axioms]
                    for axiom in axioms:
                        fol = axiom.as_fol()
                        if fol:
                            theory.add(fol)
                        owl_axioms.append(axiom)
                pds = get_module_predicate_definitions(module)
                if not theory.predicate_definitions:
                    theory.predicate_definitions = []
                existing = {pd.predicate for pd in theory.predicate_definitions}
                for pd in pds.values():
                    if pd.predicate not in existing:
                        theory.predicate_definitions.append(pd)
        return owl_axioms
