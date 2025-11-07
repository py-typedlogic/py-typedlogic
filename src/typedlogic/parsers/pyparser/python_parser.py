import logging
import os
import sys
import tempfile
from io import TextIOWrapper
from pathlib import Path
from types import ModuleType
from typing import Iterator, Optional, TextIO, Tuple, Union

from typedlogic import Theory
from typedlogic.parser import Parser, ValidationMessage
from typedlogic.parsers.pyparser.introspection import (
    get_module_predicate_definitions,
    get_module_sentence_groups,
    translate_module_to_theory, get_module_class_level_sentence_groups,
)

logger = logging.getLogger(__name__)


def compile_python(python_txt: str, name: Optional[str] = None, package_path: Optional[str] = None) -> ModuleType:
    """
    Compile a Python module from a string

    :param python_txt:
    :param package_path:
    :return:
    """
    if name is None:
        if package_path:
            name = os.path.basename(package_path).split(".")[0]
        else:
            name = "test"
    spec = compile(python_txt, name, "exec")
    module = ModuleType(name)
    if package_path:
        package_path_abs = os.path.join(os.getcwd(), package_path)
        # We have to calculate the path to expected path relative to the current working directory
        for path in sys.path:
            if package_path.startswith(path):
                path_from_tests_parent = os.path.relpath(package_path, path)
                break
            if package_path_abs.startswith(path):
                path_from_tests_parent = os.path.relpath(package_path_abs, path)
                break
        else:
            logger.warning(f"There is no established path to {package_path} - compile_python may or may not work")
            path_from_tests_parent = os.path.relpath(package_path, os.path.join(os.getcwd(), ".."))
        module.__package__ = os.path.dirname(os.path.relpath(path_from_tests_parent, os.getcwd())).replace(
            os.path.sep, "."
        )
    sys.modules[module.__name__] = module
    exec(spec, module.__dict__)
    return module


class PythonParser(Parser):
    """
    A parser for Python modules that contain axioms.

    Example:

        >>> parser = PythonParser()
        >>> theory = parser.parse(Path("tests/theorems/mortals.py"))
        >>> assert isinstance(theory, Theory)
        >>> theory.name
        'mortals'
        >>> [pd.predicate for pd in theory.predicate_definitions]
        ['Person', 'Mortal', 'AncestorOf']
        >>> for s in sorted(theory.sentences):
        ...     print(s)
        ((AncestorOf(p1, p2)) & (AncestorOf(p2, p3)) -> AncestorOf(p1, p3))
        ∀x: TreeNodeType, y: TreeNodeType : ~(AncestorOf(?x, ?y)) & (AncestorOf(?y, ?x))
        ∀x: TreeNodeType, y: TreeNodeType, z: TreeNodeType : ((AncestorOf(?x, ?z)) & (AncestorOf(?z, ?y)) -> AncestorOf(?x, ?y))
        ∀x: NameType : (Person(?x) -> Mortal(?x))

    Inheritance:

        >>> theory = parser.parse(Path("tests/theorems/class_inheritance.py"))
        >>> theory.name
        'class_inheritance'
        >>> [(pd.predicate, pd.parents) for pd in theory.predicate_definitions]
        [('Thing', []), ('Place', ['Thing']), ('Person', ['Thing'])]
        >>> from typedlogic.transformations import implies_from_parents
        >>> # TODO - consider making this default
        >>> theory = implies_from_parents(theory)
        >>> for s in sorted(theory.sentences):
        ...     print(s)
        ∀name: str, age: int : (Person(?name, ?age) -> Thing(?name))
        ∀name: str : (Place(?name) -> Thing(?name))

    """

    def transform(self, source: ModuleType, **kwargs) -> Theory:
        """
        Transform a Python module into a Theory

        :param source:
        :param kwargs:
        :return:
        """
        return translate_module_to_theory(source)

    def parse(self, source: Union[Path, str, TextIO, ModuleType], file_name: Optional[str] = None, **kwargs) -> Theory:
        """
        Parse a Python module or source code into a Theory.

        :param source:
        :param file_name:
        :param kwargs:
        :return:
        """
        if isinstance(source, ModuleType):
            return translate_module_to_theory(source)
        if self.auto_validate:
            errs = self.validate(source)
            if errs:
                raise ValueError(f"Validation errors: {errs}")
        if isinstance(source, Path):
            with source.open() as f:
                return self.parse(f, file_name=str(source), **kwargs)
        if isinstance(source, str):
            module = compile_python(source, name=None, package_path=file_name)
            sgs = get_module_sentence_groups(source)
            sgs.extend(get_module_class_level_sentence_groups(module))
            pds = get_module_predicate_definitions(module)
            # get the python module name
            return Theory(
                name=module.__name__,
                predicate_definitions=list(pds.values()),
                sentence_groups=sgs,
                source_module_name=module.__name__,
            )
        if isinstance(source, (TextIOWrapper, TextIO)):
            lines = "\n".join(source.readlines())
            return self.parse(lines, file_name=file_name, **kwargs)
        raise ValueError(f"Unsupported source type: {type(source)}")

    def validate_iter(
        self, source: Union[Path, str, TextIO, ModuleType], file_name: Optional[str] = None, **kwargs
    ) -> Iterator[ValidationMessage]:
        """
        Validate a Python module

        Note that mypy is assumed to be installed.

        Example:

            >>> import tests.theorems.animals as animals
            >>> pp = PythonParser()
            >>> pp.validate(animals)
            []

        Next we try with a deliberate error:

            >>> with open(animals.__file__) as f:
            ...    prog = f.read()
            >>> print(prog)
            <BLANKLINE>
            ...
            @dataclass
            class Likes(FactMixin):
                subject: Thing
                object: Thing
            ...


            >>> prog += "\\n@axiom\\n"
            >>> prog += "def bad_axiom(x: Thing, y: int):\\n"
            >>> prog += "    assert Likes(x, y)\\n"
            >>> errs = pp.validate(prog)
            >>> assert errs
            >>> assert "incompatible type" in errs[0].message

        :param source:
        :param file_name:
        :param kwargs:
        :return:
        """
        from mypy import api

        result: Optional[Tuple] = None
        if isinstance(source, ModuleType):
            result = api.run([str(source.__file__)])
        elif isinstance(source, str):
            with tempfile.NamedTemporaryFile(mode="w+t", delete=False) as temp_file:
                temp_file.write(source)
                temp_file.flush()
                result = api.run([temp_file.name])
        elif isinstance(source, Path):
            result = api.run([str(source)])
        if result is None:
            raise ValueError(f"Unsupported source type: {type(source)}")
        stdout, stderr, exit_code = result
        if exit_code == 0:
            return
        lines = stderr.splitlines() + stdout.splitlines()
        if not lines:
            raise ValueError(f"No output from mypy; ret={exit_code}; stdout={stdout}; stderr={stderr}")
        for line in lines:
            yield ValidationMessage(line)
