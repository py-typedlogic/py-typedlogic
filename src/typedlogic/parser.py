from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Iterator, List, Optional, TextIO, Union

from typedlogic import Sentence, Term, Theory


@dataclass
class ValidationMessage:
    """
    A message from a parser that indicates the result of a validation.
    """

    message: str
    line: Optional[int] = None
    column: Optional[int] = None
    level: str = field(default="error")

    def __str__(self):
        return f"{self.level}: {self.message} at line {self.line}, column {self.column}"

@dataclass
class Parser(ABC):
    """
    A parser is a class that can parse a source and return a Theory object.

    You can use the registry `get_parser` method to get a parser for a particular syntax:

        >>> from typedlogic.registry import get_parser
        >>> parser = get_parser("yaml")


    """

    default_suffix: ClassVar[str] = "txt"
    auto_validate: Optional[bool] = None

    def parse_file(self, source: Union[Path, str, TextIO], **kwargs) -> Theory:
        if isinstance(source, str):
            source = Path(source)
        return self.parse(source, **kwargs)

    @abstractmethod
    def parse(self, source: Union[Path, str, TextIO], **kwargs) -> Theory:
        """
        Parse a source and return a Theory object.

        :param source: A path to a file, a string representation of the source, or a file-like object.
        :param kwargs:
        :return:
        """
        pass

    def parse_sentences(self, source: Union[Path, str, TextIO], **kwargs) -> List[Sentence]:
        """
        Parse a source and return a list of sentences.

        :param source:
        :param kwargs:
        :return:
        """
        theory = self.parse(source, **kwargs)
        return theory.sentences

    def parse_ground_terms(self, source: Union[Path, str, TextIO], **kwargs) -> List[Term]:
        """
        Parse a source and return a list of sentences.

        :param source:
        :param kwargs:
        :return:
        """
        theory = self.parse(source, **kwargs)
        return theory.ground_terms

    def translate(self, source: Any, **kwargs) -> Theory:
        """
        Translate a source object into a Theory object.

        The type of the source object may be constrained by individual subclasses

        :param source:
        :param kwargs:
        :return:
        """
        raise NotImplementedError("Translation not supported by this parser")

    def validate_iter(self, source: Union[Path, str, TextIO], **kwargs) -> Iterator[ValidationMessage]:
        """
        Validate a source and return an iterator of validation messages.

        :param source:
        :param kwargs:
        :return:
        """
        return iter([])

    def validate(self, source: Union[Path, str, TextIO], **kwargs) -> List[ValidationMessage]:
        """
        Validate a source and return a list of validation messages.

        :param source:
        :param kwargs:
        :return:
        """
        return list(self.validate_iter(source, **kwargs))
