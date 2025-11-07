from io import TextIOWrapper
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO, Union

import yaml

from typedlogic import Theory
from typedlogic.parser import Parser
import typedlogic.integrations.frameworks.linkml.loader as linkml_loader
from typedlogic.parsers.pyparser import PythonParser


class LinkMLParser(Parser):
    """
    A parser for LinkML YAML files.
    """

    def parse(self, source: Union[Path, str, TextIO], **kwargs) -> Theory:
        if isinstance(source, Path):
            source = source.open()
        if not isinstance(source, (str, TextIOWrapper)):
            raise ValueError(f"Invalid source type: {type(source)}")
        obj = yaml.safe_load(source)
        python_parser = PythonParser()
        theory = python_parser.parse(linkml_loader)
        # theory = Theory()
        theory.extend(linkml_loader.generate_from_object(obj))
        return theory