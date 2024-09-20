from abc import ABC, abstractmethod
from pathlib import Path
from typing import TextIO, Union, Any, ClassVar

from typedlogic import Theory


class Parser(ABC):
    """
    A parser is a class that can parse a source and return a Theory object.

    You can use the registry `get_parser` method to get a parser for a particular syntax:

        >>> from typedlogic.registry import get_parser
        >>> parser = get_parser("yaml")


    """

    default_suffix: ClassVar[str] = "txt"

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

    def translate(self, source: Any, **kwargs) -> Theory:
        """
        Translate a source object into a Theory object.

        The type of the source object may be constrained by individual subclasses

        :param source:
        :param kwargs:
        :return:
        """
        raise NotImplementedError("Translation not supported by this parser")