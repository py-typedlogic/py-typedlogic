from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
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
        """
        Parse a file or a file-like object and return a Theory object.

        :param source:
        :param kwargs:
        :return:
        """
        if isinstance(source, str):
            source = Path(source)
        return self.parse(source, **kwargs)

    @abstractmethod
    def parse(self, source: Union[Path, str, TextIO], **kwargs) -> Theory:
        """
        Parse a source and return a Theory object.

        TODO: in future, if the source is a text representation, use parse_text() instead.

        :param source: A path to a file, a string representation of the source, or a file-like object.
        :param kwargs:
        :return:
        """
        pass

    def parse_text(self, source: str, **kwargs) -> Theory:
        """
        Parse a text string and return a Theory object.

        :param source:
        :param kwargs:
        :return:
        """
        return self.parse(source, **kwargs)

    def parse_to_sentences(self, source: Union[Path, str, TextIO], **kwargs) -> List[Sentence]:
        """
        Parse a source and return a list of sentences.

        .. note::

            This method is a convenience method that calls `parse` and returns the sentences from the resulting Theory.

        :param source:
        :param kwargs:
        :return:
        """
        theory = self.parse(source, **kwargs)
        return theory.sentences

    def parse_ground_terms(self, source: Union[Path, str, TextIO], **kwargs) -> List[Term]:
        """
        Parse a source and return a list of ground terms (facts).

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
        if isinstance(source, ModuleType):
            if not source.__file__:
                raise ValueError("Module must have a file attribute")
            return self.parse(source.__file__, **kwargs)
        raise NotImplementedError("Translation not supported by this parser")

    def validate_iter(self, source: Union[Path, str, TextIO, ModuleType], **kwargs) -> Iterator[ValidationMessage]:
        """
        Validate a source and return an iterator of validation messages.

        Validation might include type checking (for python source), syntax checking (for text source),
        linting, etc.

        :param source:
        :param kwargs:
        :return:
        """
        return iter([])

    def validate(self, source: Union[Path, str, TextIO, ModuleType], **kwargs) -> List[ValidationMessage]:
        """
        Validate a source and return a list of validation messages.

        :param source:
        :param kwargs:
        :return:
        """
        return list(self.validate_iter(source, **kwargs))
