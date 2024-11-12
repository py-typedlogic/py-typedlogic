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
    translate_module_to_theory,
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

        >>> parser = PythonParser()
        >>> theory = parser.parse(Path("tests/theorems/mortals.py"))
        >>> assert isinstance(theory, Theory)
        >>> theory.name
        'mortals'
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

        Note that mypy is assumed to be installed

        :param source:
        :param file_name:
        :param kwargs:
        :return:
        """
        from mypy import api

        result: Optional[Tuple] = None
        if isinstance(source, str):
            with tempfile.NamedTemporaryFile(mode="w+t", delete=False) as temp_file:
                temp_file.write(source)
                result = api.run([temp_file.name])
        if isinstance(source, Path):
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
