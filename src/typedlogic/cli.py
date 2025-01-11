"""
Command-line interface (CLI) for typedlogic.

To get a list of all commands:

```bash
typedlogic --help
```

Note that an easy way to use the CLI is via pipx:

```bash
pipx run typedlogic --help
```

Typically you will need one or more extras:

```bash
pipx run "typedlogic[pydantic,clingo]" --help
```

"""
from pathlib import Path
from typing import Annotated, List, Optional

import click
import typer
from typer.main import get_command

from typedlogic.registry import get_compiler, get_parser, get_solver

app = typer.Typer()

input_format_option = typer.Option(
    "python", "--input-format", "-f", help="Input format. Currently supported: python, yaml, owlpy"
)
output_format_option = typer.Option(None, "--output-format", "-t", help="Output format")

output_file_option = typer.Option(None, "--output-file", "-o", help="Output file path")


@app.command()
def convert(
    theory_files: List[Path] = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    input_format: str = input_format_option,
    output_format: str = output_format_option,
    output_file: Optional[Path] = output_file_option,
    validate_types: bool = typer.Option(
        True, "--validate-types/--no-validate-types", help="Use mypy to validate types"
    ),
):
    """
    Convert from one logic form to another.

    For a list of supported parsers and compilers,
    see https://py-typedlogic.github.io/py-typedlogic/

    Note that some conversions may be lossy. Currently no warnings are issued for such cases.

    Example:
    -------
    ```bash
    typedlogic convert  my_theory.py -t fol
    ```

    """
    parser = get_parser(input_format)
    if validate_types:
        for p in theory_files:
            errs = parser.validate(p)
            if errs:
                for err in errs:
                    click.echo(str(err))
                raise ValueError("Errors in file")
    theory = parser.parse(theory_files[0])
    if len(theory_files) > 1:
        for input_file in theory_files[1:]:
            facts_theory = parser.parse(input_file)
            for s in facts_theory.sentences:
                theory.add(s)

    compiler = get_compiler(output_format or "z3sexpr")
    result = compiler.compile(theory)

    if output_file:
        with open(output_file, "w") as f:
            f.write(result)
        typer.echo(f"Conversion result written to {output_file}")
    else:
        typer.echo(result)


def _guess_format(data_file: Path) -> str:
    suffix = data_file.suffix[1:]
    if suffix == "py":
        return "python"
    return suffix


@app.command()
def solve(
    theory_file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    solver: str = typer.Option(None, help="Solver to use"),
    check_only: bool = typer.Option(False, "--check-only", "-c", help="Check only, do not solve"),
    validate_types: bool = typer.Option(
        True, "--validate-types/--no-validate-types", help="Use mypy to validate types"
    ),
    input_format: str = input_format_option,
    data_input_format: str = typer.Option(None, "--data-input-format", "-d", help="Format for ground terms"),
    output_format: str = output_format_option,
    output_file: Optional[Path] = output_file_option,
    data_files: Annotated[Optional[List[Path]], typer.Argument()] = None,
):
    """
    Solve using the specified solver.

    Example:
    -------
    ```bash
    typedlogic solve --solver clingo my_theory.py my_data.yaml
    ```

    """
    parser = get_parser(input_format or "python")
    if validate_types:
        errs = parser.validate(theory_file)
        if errs:
            for err in errs:
                click.echo(str(err))
            raise ValueError("Errors in file")
    theory = parser.parse(theory_file)
    solver_instance = get_solver(solver or "souffle")

    if data_files:
        if theory.ground_terms is None:
            theory.ground_terms = []
        for data_file in data_files:
            data_parser = get_parser(data_input_format or _guess_format(data_file))
            terms = data_parser.parse_ground_terms(data_file)
            theory.ground_terms.extend(terms)

    solver_instance.add(theory)
    solution = solver_instance.check()

    result = f"Satisfiable: {solution.satisfiable}\n"
    if not solution.satisfiable == False and not check_only:
        for n, model in enumerate(solver_instance.models()):
            result += f"Model: {n}\n"
            for fact in model.ground_terms:
                result += f"{fact}\n"

    if output_file:
        with open(output_file, "w") as f:
            f.write(result)
        typer.echo(f"Solution written to {output_file}")
    else:
        typer.echo(result)


# DO NOT REMOVE THIS LINE
# added this for mkdocstrings to work
# see https://github.com/bruce-szalwinski/mkdocs-typer/issues/18
click_app = get_command(app)
click_app.name = "typedlogic"

if __name__ == "__main__":
    app()
