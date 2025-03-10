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