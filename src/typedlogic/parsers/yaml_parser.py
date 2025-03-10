from io import TextIOWrapper
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
        if isinstance(source, Path):
            source = source.open()
        if not isinstance(source, (str, TextIOWrapper)):
            raise ValueError(f"Invalid source type: {type(source)}")
        obj = yaml.safe_load(source)
        return from_object(obj)

    def parse_ground_terms(self, source: Union[Path, str, TextIO], **kwargs) -> List[Term]:
        """
        Parse a source and return a list of sentences.

        :param source:
        :param kwargs:
        :return:
        """
        file_name = None
        if isinstance(source, Path):
            source = source.open()
            file_name = str(source)
        if isinstance(source, str):
            file_name = source
        if not isinstance(source, (str, TextIOWrapper)):
            raise ValueError(f"Invalid source type: {type(source)}")
        obj = yaml.safe_load(source)
        if file_name:
            default_predicate = Path(file_name).stem.split(".")[0]
        else:
            default_predicate = None
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
