from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO, Union

import yaml

from typedlogic import Theory
from typedlogic.datamodel import Term, from_object
from typedlogic.parser import Parser


class YAMLParser(Parser):
    """
    A parser for YAML files.
    """

    def parse(self, source: Union[Path, str, TextIO], **kwargs) -> Theory:
        return from_object(self._load(source))

    @staticmethod
    def _load(source: Union[Path, str, TextIO]) -> Any:
        """Load YAML from a path, a YAML string, or any text stream."""
        if isinstance(source, Path):
            with source.open() as f:
                return yaml.safe_load(f)
        if not isinstance(source, str) and not hasattr(source, "read"):
            raise ValueError(f"Invalid source type: {type(source)}")
        return yaml.safe_load(source)

    def parse_ground_terms(self, source: Union[Path, str, TextIO], **kwargs) -> List[Term]:
        """
        Parse a source and return a list of sentences.

        :param source:
        :param kwargs:
        :return:
        """
        # a file named e.g. Link.01.yaml supplies "Link" as the default predicate
        default_predicate = source.name.split(".")[0] if isinstance(source, Path) else None
        obj = self._load(source)
        if isinstance(obj, list):
            return [self._ground_term(o, default_predicate) for o in obj]
        elif isinstance(obj, dict):
            terms = []
            for k, objs in obj.items():
                terms.extend([self._ground_term(o, k) for o in objs])
            return terms
        else:
            raise ValueError(f"Invalid object type: {type(obj)}")

    def _ground_term(self, obj: Union[Dict[str, Any], List[Any]], default_predicate: Optional[str] = None) -> Term:
        if isinstance(obj, dict):
            if "@type" in obj:
                default_predicate = obj["@type"]
                del obj["@type"]
            if not default_predicate:
                raise ValueError("No predicate found")
            return Term(default_predicate, obj)
        elif isinstance(obj, list):
            if not default_predicate:
                raise ValueError("No predicate found")
            return Term(default_predicate, *obj)
        else:
            raise ValueError(f"Invalid object type: {type(obj)}")
