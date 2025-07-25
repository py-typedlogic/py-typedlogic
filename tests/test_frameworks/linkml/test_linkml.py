from typing import Any, Dict, Mapping, Type, Optional

import pytest
import typedlogic.integrations.frameworks.linkml.instance as inst
import typedlogic.integrations.frameworks.linkml.loader as linkml_loader
import typedlogic.theories.jsonlog.loader as jsonlog_loader
from typedlogic import Fact, Theory
from typedlogic.compiler import write_sentences
from typedlogic.integrations.frameworks.linkml import ClassDefinition
from typedlogic.integrations.frameworks.linkml.instance import InstanceMemberType
from typedlogic.integrations.solvers.clingo.clingo_solver import ClingoSolver
from typedlogic.integrations.solvers.prover9 import Prover9Solver
from typedlogic.integrations.solvers.souffle import SouffleSolver
from typedlogic.integrations.solvers.z3 import Z3Solver
from typedlogic.parsers.pyparser.python_parser import PythonParser
from typedlogic.solver import Solver
from typedlogic.theories.jsonlog.jsonlog import NodeIsList

from tests import OUTPUT_DIR

def validate_data(schema: dict, data: dict, target_class: Optional[str] = None, solver_class: Type[Solver] = ClingoSolver) -> bool:
    """
    Validate a JSON object against a LinkML schema using a specified solver.

    :param schema:
    :param data:
    :param target_class: The class to validate against, if any
    :param solver_class:
    :return:
    """
    pp = PythonParser()
    theory = pp.transform(inst)
    theory.extend(linkml_loader.generate_from_object(schema))
    theory.extend(jsonlog_loader.generate_from_object(data))
    if target_class:
        theory.add(inst.InstanceMemberType("/", target_class))
    write_sentences(theory.sentences)
    print("PROLOG:")
    write_sentences(theory.sentences, "prolog")
    solver = solver_class()
    solver.add(theory)
    print(solver.dump())
    sat = solver.check().satisfiable
    if sat:
        print(f"ENTAILED:")
        write_sentences(solver.model().ground_terms)
    return sat is None or sat

DEFAULT_TYPES: Mapping[str, Dict[str, Any]] = {
    "string": {},
    "integer": {},
}

SCHEMA1 = {
    "classes": {
        "Thing": {},
        "Person": {
            "tree_root": True,
            "is_a": "Thing",
            "attributes": {
                "name": {
                    "identifier": True,
                    "range": "string",
                    "required": True,
                    "multivalued": False,
                },
                "address": {
                    "any_of": [
                        {"range": "Address", "inlined": False},
                        {"range": "string"},
                    ],
                },
            },
        },
        "Address": {
            "attributes": {
                "street": {
                    "range": "string",
                    "required": True,
                    "multivalued": False,
                },
            },
        },
    },
}


@pytest.mark.parametrize(
    "schema,data,valid,expected",
    [
        (
            SCHEMA1,
            {"name": "Bob"},
            True,
            [
                inst.InstanceMemberType("/", "Thing"),
                inst.InstanceMemberType("/", "Person"),
                inst.NodeIsSingleValued("/name/"),
                inst.Association("/", "name", "/name/"),
                # inst.InstanceMemberType("/name/", "string"),
                (inst.InstanceMemberType("/name/", "string"), {Z3Solver}),  # todo: unroll nested foralls
                # inst.InstanceSlotToValueNode("/", "name", "Bob"),
            ],
        ),
        (
            SCHEMA1,
            {"name": {"foo": "bar"}},
            True,
            [],
            # True, # TODO
            # [(inst.InstanceType("/name/", "string"), {Z3Solver})]
        ),
    ],
)
# @pytest.mark.parametrize("solver_class", [Z3Solver, SouffleSolver, ClingoSolver, Prover9Solver])
@pytest.mark.parametrize("solver_class", [Z3Solver, SouffleSolver, ClingoSolver])
def test_validate(solver_class, schema, data, valid, expected, request):
    if solver_class == Z3Solver:
        pytest.skip("Slow")
    id = request.node.name
    pp = PythonParser()
    theory = pp.transform(inst)
    if "types" not in schema:
        schema["types"] = DEFAULT_TYPES
    sentences = linkml_loader.generate_from_object(schema)
    for s in sentences:
        print(s)
        theory.add(s)
    sentences = jsonlog_loader.generate_from_object(data)
    for s in sentences:
        print(s)
        theory.add(s)

    solver = solver_class()
    solver.add(theory)
    if solver_class in [Z3Solver, ClingoSolver]:
        assert solver.check().satisfiable is valid
    with open(OUTPUT_DIR / f"v{id}.txt", "w") as f:
        f.write(solver.dump())
    # print(solver.dump())
    model = solver.model()
    for gt in model.ground_terms:
        print(f"Ground term: {gt}")

    expected = [e if isinstance(e, tuple) else (e, {solver_class}) for e in expected]
    expected = [e[0] for e in expected if solver_class in e[1]]
    expected = [e.to_model_object() for e in expected]
    if solver_class in [Z3Solver, Prover9Solver]:
        for e in expected:
            assert solver.prove(e)
    else:
        assert not set(expected) - set(model.ground_terms)


def test_instance_data_model():
    it = InstanceMemberType("P1", "Person")
    assert isinstance(it, Fact)
    l = NodeIsList("P1")
    cd = ClassDefinition("Person")



@pytest.mark.parametrize("solver_class", [ClingoSolver])
@pytest.mark.parametrize("required", [False, True])
@pytest.mark.parametrize("use_attributes", [False, True])
@pytest.mark.parametrize("use_subclass", [False, True])
@pytest.mark.parametrize(
    "typ,val,valid",
    [
        (None, "hello", True),
        (None, 42.1, True),
        ("string", "hello", True),
        ("string", None, True),
        ("string", 42, False),
        ("string", 42.1, False),
        ("string", False, False),
        ("integer", 42, True),
        ("integer", "42", False),
        ("integer", 42.2, False),
        ("integer", False, False),
    ],
)
# TODO
def test_basic_types(typ: str, val: Any, valid: bool, use_subclass: bool, use_attributes: bool, required: bool, solver_class):
    """
    Test basic types
    """
    from typing import Dict, Any
    schema: Dict[str, Any] = {
        "slots": {
            "s": {
                "range": typ,
                "required": required,
            }
        },
        "classes": {
            "C": {
                "slots": ["s"],
            }
        },
    }
    if use_attributes:
        schema = {
            "classes": {
                "C": {
                    "attributes": {
                        "s": {
                            "range": typ,
                            "required": required,
                        },
                    },
                }
            },
        }
    if use_subclass:
        schema["classes"]["D"] = {
            "is_a": "C",
            "slots": ["s2"],
        }
    data = {"s": val} if val is not None else {}
    if required and val is None:
        valid = False
    inst_class = "D" if use_subclass else "C"
    result = validate_data(schema, data, inst_class, solver_class)
    assert result == valid, f"Expected {valid} but got {result} for {typ} with value {val}, req: {required}"
