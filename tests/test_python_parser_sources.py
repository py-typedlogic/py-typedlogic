"""A Python theory must parse to the same Theory whether given as a file, a string or a module."""

import importlib
import json
import sys
from pathlib import Path

import pytest
from typedlogic import Term
from typedlogic.parsers.pyparser import PythonParser
from typedlogic.registry import get_solver

THEORY = """
from dataclasses import dataclass
from typedlogic import FactMixin
from typedlogic.decorators import axiom

ADULT_AGE = 18

@dataclass
class Thing(FactMixin):
    name: str

@dataclass
class Person(Thing):
    name: str

@dataclass
class Link(FactMixin):
    source: str
    target: str

@dataclass
class Path(FactMixin):
    source: str
    target: str

@dataclass
class Age(FactMixin):
    name: str
    age: int

@dataclass
class Adult(FactMixin):
    name: str

@axiom
def path_from_link(x: str, y: str):
    if Link(target=y, source=x):
        assert Path(source=x, target=y)

@axiom
def adult(x: str, a: int):
    if Age(x, a) and a >= ADULT_AGE:
        assert Adult(x)
"""


@pytest.fixture
def theory_file(tmp_path: Path) -> Path:
    path = tmp_path / "review_theory_h1.py"
    path.write_text(THEORY)
    return path


@pytest.fixture
def theory_module(theory_file: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.syspath_prepend(str(theory_file.parent))
    module = importlib.import_module(theory_file.stem)
    yield module
    sys.modules.pop(theory_file.stem, None)


def test_file_and_module_yield_the_same_theory(theory_file: Path, theory_module) -> None:
    parser = PythonParser()
    from_module = parser.parse(theory_module)
    from_file = parser.parse(theory_file)
    assert [str(s) for s in from_file.sentences] == [str(s) for s in from_module.sentences]
    assert from_file.constants == from_module.constants == {"ADULT_AGE": 18}
    assert from_file.type_definitions == from_module.type_definitions


def test_file_parse_orders_keyword_arguments_by_declaration(theory_file: Path) -> None:
    theory = PythonParser().parse(theory_file)
    solver = get_solver("clingo")
    solver.add(theory)
    solver.add(Term("Link", "a", "b"))
    solver.add(Term("Age", "bob", 30))
    solver.add(Term("Age", "kid", 3))
    solver.add(Term("Person", "fred"))
    model = solver.model()
    # Link(target=y, source=x) must not be read positionally as Link(y, x)
    assert model.retrieve("Path") == [Term("Path", "a", "b")]
    # the module-level constant is substituted, not left as an unbound variable
    assert model.retrieve("Adult") == [Term("Adult", "bob")]
    # the class hierarchy is asserted
    assert model.retrieve("Thing") == [Term("Thing", "fred")]


def test_class_hierarchy_can_be_disabled(theory_file: Path) -> None:
    theory = PythonParser().parse(theory_file, class_hierarchy=False)
    assert not any("Thing" in str(s) for s in theory.sentences)


def test_parsing_a_file_does_not_replace_an_imported_module(tmp_path: Path) -> None:
    path = tmp_path / "json.py"
    path.write_text(
        "from dataclasses import dataclass\nfrom typedlogic import FactMixin\n\n"
        "@dataclass\nclass P(FactMixin):\n    name: str\n"
    )
    theory = PythonParser().parse(path)
    assert [pd.predicate for pd in theory.predicate_definitions] == ["P"]
    assert sys.modules["json"] is json


@pytest.mark.parametrize(
    "source,expected",
    [
        (
            "from typedlogic import FactMixin\n\nclass P(FactMixin):\n"
            "    def __init__(self, name: str, n: int):\n        self.name = name\n        self.n = n\n",
            {"name": "str", "n": "int"},
        ),
        (
            "from typedlogic import FactMixin\n\nclass P(FactMixin):\n    name: str\n    n: int\n",
            {"name": "str", "n": "int"},
        ),
        (
            "from __future__ import annotations\nfrom dataclasses import dataclass\nfrom typedlogic import FactMixin\n\n"
            "@dataclass\nclass P(FactMixin):\n    name: str\n    n: int\n",
            {"name": "str", "n": "int"},
        ),
        (
            "from typing import Optional\nfrom dataclasses import dataclass\nfrom typedlogic import FactMixin\n\n"
            "@dataclass\nclass P(FactMixin):\n    name: Optional[str]\n    n: int | None\n",
            {"name": "str", "n": "int"},
        ),
    ],
    ids=["plain-init", "plain-annotated", "future-annotations", "optional"],
)
def test_predicate_arguments_are_introspected(source: str, expected: dict) -> None:
    theory = PythonParser().parse(source)
    assert theory.predicate_definition_map["P"].arguments == expected


def test_union_alias_and_non_literal_module_values() -> None:
    source = (
        "import logging\nfrom dataclasses import dataclass\nfrom typedlogic import FactMixin\n\n"
        "logger = logging.getLogger(__name__)\nIntOrStr = int | str\nLIMIT = 3\n\n"
        "@dataclass\nclass P(FactMixin):\n    name: str\n"
    )
    theory = PythonParser().parse(source)
    assert theory.type_definitions["IntOrStr"] == ["int", "str"]
    assert theory.constants == {"LIMIT": 3}


AXIOM_FORMS = '''
import typedlogic
from dataclasses import dataclass
from typedlogic import FactMixin, axiom

@dataclass
class P(FactMixin):
    name: str

@dataclass
class Q(FactMixin):
    name: str

@axiom
def bare_expression(x: str):
    """A docstring is not an axiom."""
    P(x) >> Q(x)

@typedlogic.axiom
def qualified_decorator(x: str):
    if Q(x):
        assert P(x)
'''


def test_bare_expression_bodies_and_qualified_decorators_are_axioms() -> None:
    theory = PythonParser().parse(AXIOM_FORMS)
    groups = {sg.name: [str(s) for s in sg.sentences or []] for sg in theory.sentence_groups}
    assert groups["bare_expression"] == ["∀x: str : (P(?x) -> Q(?x))"]
    assert groups["qualified_decorator"] == ["∀x: str : (Q(?x) -> P(?x))"]


def test_unsupported_axiom_statement_is_an_error() -> None:
    source = AXIOM_FORMS + "\n@axiom\ndef loop(x: str):\n    for y in [x]:\n        assert P(y)\n"
    with pytest.raises(ValueError, match="Unsupported statement in loop"):
        PythonParser().parse(source)
