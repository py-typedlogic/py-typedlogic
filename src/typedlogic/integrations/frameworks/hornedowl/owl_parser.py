from pathlib import Path
from types import ModuleType
from typing import List, Optional, Set, TextIO, Type, Union

from typedlogic import Theory
from typedlogic.integrations.frameworks.hornedowl.horned_owl_bridge import parse_owl_ontology_to_theory
from typedlogic.parser import Parser


def _get_all_subclasses(cls: Type) -> Set[Type]:
    subclasses = set(cls.__subclasses__())
    return subclasses.union(s for c in subclasses for s in _get_all_subclasses(c))


class OWLParser(Parser):
    """
    A parser that converts OWL ontologies expressed in a standard OWL syntax.

    Py-horned OWL is used

    Example:
    -------
        >>> from typedlogic.transformations import as_fol
        >>> parser = OWLParser()

    Usage on the command line:

        typedlogic convert -f owl ro.ofn -t prolog


    """

    def parse(
        self, source: Union[Path, str, TextIO], include_all=False, modules: Optional[List[ModuleType]] = None, **kwargs
    ) -> Theory:
        """
        Parse the source into a theory.

        >>> parser = OWLParser()
        >>> theory = parser.parse("tests/test_frameworks/hornedowl/input/ro.ofn")
        >>> for pd in theory.predicate_definitions:
        ...     print(pd.predicate, pd.parents)
        <BLANKLINE>
        ...
        continuant ['Thing']
        ...
        <BLANKLINE>
        >>> for s in theory.sentences:
        ...     print(s)
        <BLANKLINE>
        ...
        ∀I: None, J: None : (surrounded_by(?I, ?J) <-> surrounds(?J, ?I))
        ...
        <BLANKLINE>

        :param source:
        :param include_all:
        :param modules:
        :param kwargs:
        :return:
        """
        if isinstance(source, Path):
            source = str(source)
        if not isinstance(source, str):
            raise NotImplementedError("Only file paths are supported")
        if not Path(source).exists():
            raise FileNotFoundError(f"File not found: {source}")
        return parse_owl_ontology_to_theory(source)
