import importlib
import inspect
import logging
import os
from pathlib import Path
from typing import Dict, Type, Union, Tuple

from attr import dataclass

import typedlogic
from typedlogic.compiler import Compiler
from typedlogic.parser import Parser
from typedlogic.solver import Solver

logger = logging.getLogger(__name__)

SUFFIXES = {
    Compiler: "compiler",
    Parser: "parser",
    Solver: "solver"
}

Extendable = Union[Compiler, Parser, Solver]


@dataclass
class Registry:
    implementation_classes: Dict[Type, Dict[str, Type]] = {}

    def register(self, name: str, category: Type, impl_class: Type[Extendable]):
        if category not in self.implementation_classes:
            self.implementation_classes[category] = {}
        self.implementation_classes[category][name] = impl_class

    def get_implementation_class(self, category: Type, name: str) -> Type[Extendable]:
        if category not in self.implementation_classes:
            raise ValueError(f"Unknown category: {category}\n" 
                             f"Known categories: {list(self.implementation_classes.keys())}")
        if name not in self.implementation_classes[category]:
            raise ValueError(f"Unknown handle: {name}\n" 
                             f"Known implementations: {list(self.implementation_classes[category].keys())}")
        return self.implementation_classes[category][name]

    def create_instance(self, category: Type, handle: str, **kwargs) -> Extendable:
        implementation_class = self.get_implementation_class(category, handle)
        return implementation_class()

    @classmethod
    def load_implementations(cls, package_path: str):
        registry = cls()
        this_path = importlib.import_module(package_path).__file__
        if this_path is None:
            raise ValueError(f"Error: package {package_path} not found")
        package_dir = os.path.dirname(Path(this_path))
        # traverse the directory recursively
        for root, dirs, files in os.walk(package_dir):
            for filename in files:
                filepath = os.path.join(root, filename)
                if filepath.endswith(".py") and not filepath.startswith("__"):
                    base = filepath.replace(package_dir, "").replace("/", ".")[1:-3]
                    module_name = f"{package_path}.{base}"
                    try:
                        module = importlib.import_module(module_name)
                        for name, obj in inspect.getmembers(module):
                            if inspect.isclass(obj):
                                for t, suffix_name in SUFFIXES.items():
                                    if name.lower().endswith(suffix_name) and issubclass(obj, t):
                                        handle = name.lower().replace(suffix_name, "")
                                        registry.register(handle, t, obj)
                    except ImportError as e:
                        logger.info(f"Error importing {module_name}: {e} - assuming not installed")
        return registry


registry = Registry.load_implementations("typedlogic")

def get_compiler(handle: str, **kwargs) -> Compiler:
    """
    Get a compiler

    >>> from typedlogic.registry import get_compiler
    >>> z3_compiler = get_compiler('z3')
    >>> type(z3_compiler)
    <class 'typedlogic.integrations.solvers.z3.z3_compiler.Z3Compiler'>

    :param handle:
    :param kwargs:
    :return:
    """
    return registry.create_instance(Compiler, handle, **kwargs)


def get_solver(handle: str, **kwargs) -> Solver:
    """
    Get a solver

    >>> from typedlogic.registry import get_solver
    >>> z3_solver = get_solver('z3')
    >>> type(z3_solver)
    <class 'typedlogic.integrations.solvers.z3.z3_solver.Z3Solver'>

    :param handle:
    :param kwargs:
    :return:
    """
    return registry.create_instance(Solver, handle, **kwargs)


def get_parser(handle: str, **kwargs) -> Parser:
    """
    Get a parser

    >>> from typedlogic.registry import get_parser
    >>> python_parser = get_parser('python')
    >>> type(python_parser)
    <class 'typedlogic.parsers.pyparser.python_parser.PythonParser'>
    """
    return registry.create_instance(Parser, handle, **kwargs)
