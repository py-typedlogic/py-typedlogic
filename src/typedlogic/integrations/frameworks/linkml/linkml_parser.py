from pathlib import Path
from typing import TextIO, Union

import yaml

from typedlogic import Theory
from typedlogic.integrations.frameworks.linkml.reasoning import schema_theory_from_object
from typedlogic.parser import Parser


class LinkMLParser(Parser):
    """A parser for LinkML YAML schema files."""

    def parse(self, source: Union[Path, str, TextIO], **kwargs) -> Theory:
        if isinstance(source, Path):
            text = source.read_text(encoding="utf-8")
        elif hasattr(source, "read"):
            text = source.read()
        elif isinstance(source, str):
            text = source
        else:
            raise ValueError(f"Invalid source type: {type(source)}")
        obj = yaml.safe_load(text)
        return schema_theory_from_object(obj, include_schema_rules=kwargs.get("include_schema_rules", True))
