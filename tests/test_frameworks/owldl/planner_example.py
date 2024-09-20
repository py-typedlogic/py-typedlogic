from abc import ABC, abstractmethod

from typedlogic import Sentence, Variable
from typedlogic.datamodel import And, term
from typedlogic.integrations.frameworks.owldl import IRI, Thing, TopDataProperty


class FilesystemNode(Thing):
    """An entity in a filesystem with a distinct address."""

class Directory(FilesystemNode):
    """A filesystem node that can contain other nodes."""

class File(FilesystemNode):
    """A filesystem node that contains data."""

class FileContents(TopDataProperty):
    """The data contained in a file."""

    domain = File
    range = str

class Action(Thing, ABC):
    """An action has pre and post conditions."""

    @abstractmethod
    def preconditions(self) -> Sentence:
        pass

    @abstractmethod
    def postconditions(self) -> Sentence:
        pass

class CreateFile(Action):
    """Create a file."""

    node: IRI

    def preconditions(self) -> Sentence:
        return ~File(self.node).to_model_object()

    def postconditions(self) -> Sentence:
        return File(self.node).to_model_object()


class DeleteFile(Action):
    """Delete a file."""

    node: IRI

    def preconditions(self) -> Sentence:
        return File(self.node).to_model_object()

    def postconditions(self) -> Sentence:
        return ~File(self.node).to_model_object()

class CopyFile(Action):
    """Copy a file."""

    source: IRI
    target: IRI

    def preconditions(self) -> Sentence:
        return File(self.source).to_model_object()

    def postconditions(self) -> Sentence:
        s = self.source
        t = self.target
        c = Variable("c", "str")
        return And(
            term(File, s),
            term(File, t),
            term(FileContents, s, c),
            term(FileContents, t, c)
        )


