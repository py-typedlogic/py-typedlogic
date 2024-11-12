import pytest

from tests.theorems import unary_predicates
from tests.theorems.probabilistic import coins2
from typedlogic.compilers.fol_compiler import FOLCompiler
from typedlogic.compilers.prolog_compiler import PrologCompiler
from typedlogic.compilers.prover9_compiler import Prover9Compiler
from typedlogic.compilers.sexpr_compiler import SExprCompiler
from typedlogic.compilers.tptp_compiler import TPTPCompiler
from typedlogic.compilers.yaml_compiler import YAMLCompiler
from typedlogic.integrations.solvers.problog.problog_compiler import ProbLogCompiler
from typedlogic.integrations.solvers.souffle.souffle_compiler import SouffleCompiler
from typedlogic.integrations.solvers.z3.z3_compiler import Z3Compiler, Z3FunctionalCompiler, Z3SExprCompiler
from typedlogic.parsers.pyparser.introspection import translate_module_to_theory

import tests.theorems.animals as animals
import tests.theorems.defined_types_example as defined_types_example
import tests.theorems.import_test.ext as import_test_ext
import tests.theorems.mortals as mortals
import tests.theorems.numbers as numbers
import tests.theorems.optional_example as optional_example
import tests.theorems.paths as paths
import tests.theorems.paths_with_distance as pwd
import tests.theorems.simple_contradiction as simple_contradiction
import tests.theorems.types_example as types_example
from tests import SNAPSHOTS_DIR


@pytest.mark.parametrize(
    "compiler_class",
    [
        FOLCompiler,
        Z3SExprCompiler,
        Z3FunctionalCompiler,
        PrologCompiler,
        SouffleCompiler,
        TPTPCompiler,
        Prover9Compiler,
        YAMLCompiler,
        SExprCompiler,
        ProbLogCompiler,
    ],
)
@pytest.mark.parametrize(
    "theory_module",
    [
        pwd,
        mortals,
        animals,
        types_example,
        defined_types_example,
        import_test_ext,
        numbers,
        paths,
        optional_example,
        simple_contradiction,
        unary_predicates,
    ],
)
def test_compiler(compiler_class, theory_module):
    if issubclass(compiler_class, Z3Compiler) and theory_module == defined_types_example:
        pytest.skip("Z3Solver does not support defined types")
    if issubclass(compiler_class, Z3Compiler) and theory_module == optional_example:
        pytest.skip("Z3Solver does not support defined Optional")
    theory = translate_module_to_theory(theory_module)
    compiler = compiler_class()
    compiled = compiler.compile(theory)
    print(compiled)
    fn = f"{theory_module.__name__}-{compiler_class.__name__}.{compiler.suffix}"
    with open(SNAPSHOTS_DIR / fn, "w", encoding="utf-8") as f:
        f.write(compiled)
    if compiler_class.parser_class is not None:
        parser = compiler_class.parser_class()
        parser.parse(compiled)
        with open(SNAPSHOTS_DIR / fn) as f:
            roundtripped = parser.parse(f)
            # assert roundtripped == compiled
            compiled2 = compiler.compile(roundtripped)
            assert compiled2 == compiled
