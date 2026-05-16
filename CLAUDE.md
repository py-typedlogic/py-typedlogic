# Python TypedLogic Development Guide

## Commands
- **Install**: `uv sync --all-extras --dev`
- **Build**: `uv build`
- **Run all tests**: `uv run pytest` or `make test`
- **Run single test**: `uv run pytest tests/path/to/test_file.py::test_function_name`
- **Run tests by pattern**: `uv run pytest -k "pattern"`
- **Type check**: `uv run mypy src tests`
- **Lint**: `uv run ruff check src/ tests/ --exclude tests/input --exclude tests/output`
- **Format code**: `uv run black src/ tests/ --exclude "/(tests/input|tests/output)/"`
- **Fix linting**: `uv run tox -e lint-fix`
- **Spell check**: `uv run tox -e codespell`
- **Update dependencies**: `uv lock --upgrade`

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
- If uv reports that the lockfile is stale, run `uv lock` to refresh it
- When tests fail with specific solvers, try Z3Solver which has the broadest support
- For CI pipeline issues, check the GitHub Actions log for specific error messages
