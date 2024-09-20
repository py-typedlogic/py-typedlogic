from io import TextIOWrapper
from pathlib import Path
from typing import TextIO, Union

import yaml

from typedlogic import Theory
from typedlogic.datamodel import from_object
from typedlogic.parser import Parser


class YAMLParser(Parser):
    """
    A parser for YAML files.
    """

    def parse(self, source: Union[Path, str, TextIO], **kwargs) -> Theory:
        if isinstance(source, Path):
            source = source.open()
        if not isinstance(source, (str, TextIOWrapper)):
            raise ValueError(f"Invalid source type: {type(source)}")
        obj = yaml.safe_load(source)
        return from_object(obj)
