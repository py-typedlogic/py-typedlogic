import pytest
from typedlogic.integrations.frameworks.hornedowl.owl_compiler import OWLCompiler
from typedlogic.integrations.frameworks.hornedowl.owl_parser import OWLParser
from typedlogic.integrations.frameworks.owldl import OWLPyParser
from typedlogic.registry import get_compiler

import tests.test_frameworks.owldl.family as family
import tests.test_frameworks.owldl.paths_owldl as paths_owldl
from tests.test_frameworks.hornedowl import HORNEDOWL_INPUT_DIR, HORNEDOWL_OUTPUT_DIR

RO = HORNEDOWL_INPUT_DIR / "ro.ofn"


@pytest.mark.parametrize(
    "input_path",
    [
        RO,
    ],
)
def test_convert_owlpy_to_owl(input_path):
    parser = OWLParser()
    theory = parser.parse(input_path)
    # for s in theory.sentences:
    #    print(s, s.annotations["owl_axiom"])
    compiler = OWLCompiler()
    out = compiler.compile(theory)
    print(out)


@pytest.mark.parametrize(
    "module",
    [
        family,
        paths_owldl,
    ],
)
def test_convert_native_to_owl(module):
    parser = OWLPyParser()
    theory = parser.translate(module)
    module_name = module.__name__.split(".")[-1]
    for s in theory.sentences:
        print(s, s.annotations["owl_axiom"])
    compiler = OWLCompiler()
    out = compiler.compile(theory)
    # print(out)
    output_path = HORNEDOWL_OUTPUT_DIR / f"{module_name}.ofn"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(out)
    # ensure no cross-ontology leakage
    if module == family:
        assert "Path" not in out
        assert "EquivalentClasses(Parent ObjectIntersectionOf(Person ObjectSomeValuesFrom(HasChild Thing)))" in out
    elif module == paths_owldl:
        assert "Parent" not in out
        assert "TransitiveObjectProperty(Path)" in out
    else:
        assert False


@pytest.mark.parametrize(
    "module",
    [
        family,
    ],
)
@pytest.mark.parametrize(
    "output_format",
    [
        "fol",
        "prolog",
        "sexpr",
        "owl",
    ],
)
def test_convert_native_to_fol(module, output_format):
    parser = OWLPyParser()
    theory = parser.translate(module)
    module_name = module.__name__.split(".")[-1]
    compiler = get_compiler(output_format)
    out = compiler.compile(theory)
    print(out)
    output_path = HORNEDOWL_OUTPUT_DIR / f"{module_name}.{output_format}"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(out)
