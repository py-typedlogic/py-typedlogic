import pytest
from typedlogic.evaluation import randomize_entity_names, run_benchmark
from typedlogic.integrations.solvers.clingo import ClingoSolver
from typedlogic.integrations.solvers.souffle import SouffleSolver
from tests.conftest import has_souffle


@pytest.mark.parametrize("randomize", [False, True])
def test_create_benchmark(randomize, path_benchmark):
    benchmark = path_benchmark
    if randomize:
        randomize_entity_names(benchmark)
    
    # Define solvers to test
    solvers = [ClingoSolver]
    if has_souffle:
        solvers.append(SouffleSolver)
    
    for sc in solvers:
        result = run_benchmark(benchmark, sc)
        assert result.score == 1.0
