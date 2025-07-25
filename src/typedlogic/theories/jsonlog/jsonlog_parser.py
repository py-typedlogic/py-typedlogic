from io import TextIOWrapper
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO, Union

import json

from typedlogic import Theory
from typedlogic.parser import Parser
import typedlogic.theories.jsonlog.loader as jsonlog_loader


class JsonLogParser(Parser):
    """
    A parser for JsonLog JSON files.
    """

    def parse(self, source: Union[Path, str, TextIO], **kwargs) -> Theory:
        if isinstance(source, Path):
            source = source.open()
        if not isinstance(source, (str, TextIOWrapper)):
            raise ValueError(f"Invalid source type: {type(source)}")
        obj = json.loads(source)
        theory = Theory()
        theory.extend(jsonlog_loader.generate_from_object(obj))
        return theory