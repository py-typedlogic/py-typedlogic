# Python TypedLogic Development Guide

## Commands
- **Install**: `poetry install`
- **Build**: `poetry build`
- **Run all tests**: `poetry run pytest` or `make test`
- **Run single test**: `poetry run pytest tests/path/to/test_file.py::test_function_name`
- **Run tests by pattern**: `poetry run pytest -k "pattern"`
- **Type check**: `poetry run mypy src tests`
- **Lint**: `poetry run ruff check src/ tests/ --exclude tests/input --exclude tests/output`
- **Format code**: `poetry run black src/ tests/ --exclude "/(tests/input|tests/output)/"`
- **Fix linting**: `poetry run tox -e lint-fix`
- **Spell check**: `poetry run tox -e codespell`
- **Update dependencies**: `poetry update`

## Style Guidelines
- Python 3.10+ with strict typing
- Line length: 120 characters
- Use type annotations everywhere, checked with mypy
- snake_case for functions/variables, PascalCase for classes
- Docstrings required (checked by docstr-coverage)
- Import order: stdlib → third-party → local
- Follow PEP 8 conventions with Black formatting
- Max complexity: 10 (McCabe)
- Prefer explicit error handling with specific exceptions

## TypedLogic Framework Patterns
- Classes inherit from `FactMixin` to participate in logical reasoning
- Use `@axiom` decorator for defining logical rules
- Use `@goal` decorator for defining provable assertions
- Implications use the `>>` operator (e.g., `A() >> B()`)
- Conjunctions use the `&` operator (e.g., `A() & B()`)
- Negations use the `~` operator (e.g., `~A()`)
- Class inheritance is supported (e.g., `class Male(Person): ...`)
- Z3Solver works well for most examples, especially with class hierarchies
- When creating tests, use `solver.load(module)` to import all axioms

## Troubleshooting
- For codespell issues, add words to ignore-words-list in pyproject.toml
- If Poetry has hash verification issues, run `poetry update` to refresh the lock file
- When tests fail with specific solvers, try Z3Solver which has the broadest support
- For CI pipeline issues, check the GitHub Actions log for specific error messages