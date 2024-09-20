
import pytest
from typedlogic.evaluation import randomize_entity_names, run_benchmark
from typedlogic.integrations.solvers.clingo import ClingoSolver
from typedlogic.integrations.solvers.souffle import SouffleSolver


@pytest.mark.parametrize("randomize", [False, True])
def test_create_benchmark(randomize, path_benchmark):
    benchmark = path_benchmark
    if randomize:
        randomize_entity_names(benchmark)
    for sc in [SouffleSolver, ClingoSolver]:
        result = run_benchmark(benchmark, sc)
        assert result.score == 1.0




