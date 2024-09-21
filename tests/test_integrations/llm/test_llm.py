import pytest
from typedlogic.evaluation import create_random_id_function, randomize_entity_names, run_benchmark


@pytest.mark.llm
@pytest.mark.parametrize("randomize", [False, True])
@pytest.mark.parametrize("model_name", ["o1-preview", "lbl/gpt-4o", "lbl/claude-opus"])
def test_path_benchmark(path_benchmark_d5, randomize, model_name):
    from typedlogic.integrations.solvers.llm.llm_solver import LLMSolver
    benchmark = path_benchmark_d5
    if randomize:
        f = create_random_id_function(prefix="e")
        randomize_entity_names(benchmark, f)
    #for g in path_benchmark.goals:
    #    print(g)
    result = run_benchmark(benchmark, LLMSolver)
    print(f"MODEL {model_name} RAND: {randomize} ENTITIES: {len(benchmark.entities)} SCORE: {result.score}")
