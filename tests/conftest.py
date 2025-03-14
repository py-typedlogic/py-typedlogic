import shutil
from random import randint
from typing import List

import pytest
from typedlogic import Sentence
from typedlogic.evaluation import Benchmark, BenchmarkSeed, benchmark_from_seed
from typedlogic.parsers.pyparser import PythonParser

from tests import tree_edges

# Check for external dependencies
has_prover9 = shutil.which("prover9") is not None
has_souffle = shutil.which("souffle") is not None
has_clingo = True  # Assuming Python package is installed via poetry

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "prover9: mark tests requiring prover9 executable")
    config.addinivalue_line("markers", "souffle: mark tests requiring souffle executable")
    config.addinivalue_line("markers", "slow: mark test as slow running")

def pytest_collection_modifyitems(config, items):
    """Skip tests based on available executables and other markers."""
    # Skip markers
    skip_souffle = pytest.mark.skip(reason="Souffle executable not found")
    skip_prover9 = pytest.mark.skip(reason="Prover9 executable not found")
    skip_slow = pytest.mark.skip(reason="slow test")
    
    for item in items:
        # Skip slow tests
        if item.get_closest_marker("slow"):
            item.add_marker(skip_slow)
            
        # Skip tests requiring external executables if not available
        if item.get_closest_marker("souffle") or "souffle" in str(item.nodeid).lower():
            if not has_souffle:
                item.add_marker(skip_souffle)
                
        if item.get_closest_marker("prover9") or "prover9" in str(item.nodeid).lower():
            if not has_prover9:
                item.add_marker(skip_prover9)


@pytest.fixture
def path_benchmark() -> Benchmark:
    return _path_benchmark(depth=3)


@pytest.fixture
def path_benchmark_d4() -> Benchmark:
    return _path_benchmark(depth=4)


@pytest.fixture
def path_benchmark_d5() -> Benchmark:
    return _path_benchmark(depth=5)


def _path_benchmark(depth=3) -> Benchmark:
    from tests.theorems import paths

    parser = PythonParser()
    theory = parser.parse(paths)
    print("Parsed theory")
    ground_terms: List[Sentence] = []
    seed = BenchmarkSeed(
        theory=theory,
    )
    entities = set()
    for source, target in tree_edges("a", depth, 3):
        ground_terms.append(paths.Link(source=source, target=target))
        entities.update({source, target})
    seed.ground_terms = ground_terms
    entities_l = list(entities)

    def rand_entity() -> str:
        return entities_l[randint(0, len(entities_l) - 1)]

    candidate_goals: List[Sentence] = []
    for n in range(0, 20):
        candidate_goals.append(paths.Path(source=rand_entity(), target=rand_entity()))
    seed.candidate_goals = candidate_goals
    benchmark = benchmark_from_seed(seed)
    benchmark.entities = entities_l
    return benchmark
