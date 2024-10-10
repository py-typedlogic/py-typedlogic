from typing import Any, Dict, Mapping

import pytest
import typedlogic.integrations.frameworks.linkml.instance as inst
import typedlogic.integrations.frameworks.linkml.loader as linkml_loader
import typedlogic.theories.jsonlog.loader as jsonlog_loader
from typedlogic import Fact
from typedlogic.integrations.frameworks.linkml import ClassDefinition
from typedlogic.integrations.frameworks.linkml.instance import InstanceMemberType
from typedlogic.integrations.solvers.clingo.clingo_solver import ClingoSolver
from typedlogic.integrations.solvers.prover9 import Prover9Solver
from typedlogic.integrations.solvers.souffle import SouffleSolver
from typedlogic.integrations.solvers.z3 import Z3Solver
from typedlogic.parsers.pyparser.python_parser import PythonParser
from typedlogic.theories.jsonlog.jsonlog import NodeIsList

from tests import OUTPUT_DIR

DEFAULT_TYPES: Mapping[str, Dict[str, Any]] = {
    "string": {},
    "integer": {},
}

SCHEMA1 = {
             "classes": {
                    "Thing": {
                    },
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
                                    {"range": "Address",
                                     "inlined": False},
                                    {"range": "string"},
                                ],
                            }
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

@pytest.mark.parametrize("schema,data,valid,expected",
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
                                        #inst.InstanceSlotToValueNode("/", "name", "Bob"),
                                 ]
                             ),
                            (
                                 SCHEMA1,
                                 {"name": {"foo": "bar"}},
                                True,
                                [],
                                 #True, # TODO
                                 #[(inst.InstanceType("/name/", "string"), {Z3Solver})]
                             ),
                         ]
                         )
#@pytest.mark.parametrize("solver_class", [Z3Solver, SouffleSolver, ClingoSolver, Prover9Solver])
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
    expected = [e[0] for e in expected  if solver_class in e[1]]
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




