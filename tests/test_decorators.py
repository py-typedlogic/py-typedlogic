from dataclasses import FrozenInstanceError, dataclass
from pathlib import Path

import pytest
from typedlogic import FactMixin
from typedlogic.decorators import predicate
from typedlogic.parsers.pyparser.python_parser import PythonParser


@predicate
class Person:
    name: str
    age: int

@dataclass
class Animal(FactMixin):
    name: str
    species: str


def test_predicate():
    p = Person("Alice", 42)
    assert p.name == "Alice"
    assert p.age == 42
    assert str(p) == "Person(name='Alice', age=42)"
    assert repr(p) == "Person(name='Alice', age=42)"
    assert p == Person("Alice", 42)
    assert p != Person("Bob", 42)
    assert p != Person("Alice", 43)
    assert p != Person("Bob", 43)
    assert hash(p) == hash(Person("Alice", 42))
    assert hash(p) != hash(Person("Bob", 42))
    assert hash(p) != hash(Person("Alice", 43))
    assert hash(p) != hash(Person("Bob", 43))
    assert p.__annotations__ == {"name": str, "age": int}
    assert isinstance(p, FactMixin)
    with pytest.raises(FrozenInstanceError):
        p.age = 43

def test_pyparse():
    p = PythonParser()
    p.parse("1 + 2")
    p.parse("1 + 2 + 3")
    theory = p.parse(Path(__file__))
    assert theory.predicate_definitions
    assert len(theory.predicate_definitions) == 2
    [person_def] = [pd for pd in theory.predicate_definitions if pd.predicate == "Person"]
    assert person_def
    # TODO: use strings for arguments
    assert person_def.arguments == {"name": 'str', "age": 'int'}


