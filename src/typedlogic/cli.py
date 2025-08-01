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

from typedlogic.registry import get_compiler, get_parser, get_solver, all_parser_classes, all_compiler_classes, all_solver_classes

app = typer.Typer()

input_format_option = typer.Option(
    "python", "--input-format", "-f", help="Input format. Currently supported: python, yaml, owlpy"
)
output_format_option = typer.Option(None, "--output-format", "-t", help="Output format")

output_file_option = typer.Option(None, "--output-file", "-o", help="Output file path")

@app.command()
def list_parsers():
    """
    Lists all parsers.

    Anything here should be usable as an input format.
    """
    for name, cls in all_parser_classes().items():
        print(name, cls)


@app.command()
def list_compilers():
    """
    Lists all compilers.

    Anything here should be usable as an output format.
    """
    for name, cls in all_compiler_classes().items():
        print(name, cls)


@app.command()
def list_solvers():
    """
    Lists all solvers.

    Anything here should be usable as a solver.
    """
    for name, cls in all_solver_classes().items():
        print(name, cls)


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
    # Check for catalog files first
    if data_file.name.endswith('.catalog.yaml') or data_file.name.endswith('.catalog.yml'):
        return "catalog"
    
    suffix = data_file.suffix[1:]
    if suffix == "py":
        return "python"
    elif suffix in ["csv", "tsv", "xlsx", "xls", "tab"]:
        return "dataframe"
    return suffix


def _combine_input_files(input_files: List[Path], validate_types: bool = True):
    """
    Combine multiple input files into a single theory.
    
    Args:
    ----
        input_files: List of file paths to combine
        validate_types: Whether to validate Python files with mypy
        
    Returns:
    -------
        Combined theory object
        
    Raises:
    ------
        ValueError: If validation fails or no valid theories found

    """
    combined_theory = None

    for input_file in input_files:
        file_format = _guess_format(input_file)
        parser = get_parser(file_format)

        if validate_types and file_format == "python":
            errs = parser.validate(input_file)
            if errs:
                for err in errs:
                    click.echo(f"Validation error in {input_file}: {err}")
                raise ValueError(f"Type validation errors in {input_file}")

        # Parse the file - try theory first, then ground terms
        if combined_theory is None:
            try:
                parsed_result = parser.parse(input_file)
                # Check if result is a proper Theory object
                if hasattr(parsed_result, 'sentences') or hasattr(parsed_result, 'predicate_definitions'):
                    combined_theory = parsed_result
                else:
                    # Result is raw data, treat as ground terms
                    from typedlogic import Theory
                    combined_theory = Theory()
                    ground_terms = parser.parse_ground_terms(input_file)
                    combined_theory.ground_terms = ground_terms
            except Exception:
                # If parsing as theory fails, try as ground terms only
                from typedlogic import Theory
                combined_theory = Theory()
                ground_terms = parser.parse_ground_terms(input_file)
                combined_theory.ground_terms = ground_terms
        else:
            # Try to parse as theory first
            try:
                parsed_result = parser.parse(input_file)
                # Check if result is a proper Theory object
                if hasattr(parsed_result, 'sentences') or hasattr(parsed_result, 'predicate_definitions'):
                    file_theory = parsed_result

                    # Merge sentences (axioms)
                    if hasattr(file_theory, 'sentences') and file_theory.sentences:
                        if combined_theory.sentences is None:
                            combined_theory.sentences = []
                        combined_theory.sentences.extend(file_theory.sentences)

                    # Merge ground terms (facts)
                    if hasattr(file_theory, 'ground_terms') and file_theory.ground_terms:
                        if combined_theory.ground_terms is None:
                            combined_theory.ground_terms = []
                        combined_theory.ground_terms.extend(file_theory.ground_terms)

                    # Merge predicate definitions
                    if hasattr(file_theory, 'predicate_definitions') and file_theory.predicate_definitions:
                        if combined_theory.predicate_definitions is None:
                            combined_theory.predicate_definitions = []
                        # Avoid duplicates by name
                        existing_names = {pd.predicate for pd in combined_theory.predicate_definitions}
                        for pd in file_theory.predicate_definitions:
                            if pd.predicate not in existing_names:
                                combined_theory.predicate_definitions.append(pd)
                else:
                    # Result is raw data, treat as ground terms
                    ground_terms = parser.parse_ground_terms(input_file)
                    if combined_theory.ground_terms is None:
                        combined_theory.ground_terms = []
                    combined_theory.ground_terms.extend(ground_terms)
            except Exception:
                # If parsing as theory fails, try as ground terms
                ground_terms = parser.parse_ground_terms(input_file)
                if combined_theory.ground_terms is None:
                    combined_theory.ground_terms = []
                combined_theory.ground_terms.extend(ground_terms)

    if combined_theory is None:
        raise ValueError("No valid theories found in input files")

    return combined_theory


@app.command()
def solve(
    theory_file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    solver: str = typer.Option("souffle", "--solver", "-s", help="Solver to use (z3, souffle, clingo, etc.)"),
    check_only: bool = typer.Option(False, "--check-only", "-c", help="Check satisfiability only, do not enumerate models"),
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
    Solve logical theories with facts using the specified solver.
    
    Accepts a theory file and optional data files containing facts.
    Files can be Python (.py) or YAML (.yaml) format - format is auto-detected.
    
    First checks satisfiability, then enumerates all models if satisfiable.

    Examples
    --------
    ```bash
    # Solve with theory and facts
    typedlogic solve theory.py facts.yaml --solver z3
    
    # Check satisfiability only
    typedlogic solve theory.py --check-only
    
    # Solve with multiple data files
    typedlogic solve theory.py data1.yaml data2.yaml --solver z3
    ```

    """
    # Parse theory file
    parser = get_parser(input_format or "python")
    if validate_types:
        errs = parser.validate(theory_file)
        if errs:
            for err in errs:
                click.echo(f"Validation error in {theory_file}: {err}")
            raise typer.Exit(1)
    
    combined_theory = parser.parse(theory_file)
    
    # Parse data files and add ground terms
    if data_files:
        if combined_theory.ground_terms is None:
            combined_theory.ground_terms = []
        for data_file in data_files:
            data_parser = get_parser(data_input_format or _guess_format(data_file))
            terms = data_parser.parse_ground_terms(data_file)
            combined_theory.ground_terms.extend(terms)

    # Initialize solver
    try:
        solver_instance = get_solver(solver or "souffle")
    except ValueError as e:
        click.echo(f"Error: {e}")
        raise typer.Exit(1)

    # Load theory into solver
    solver_instance.add(combined_theory)

    # Check satisfiability first
    click.echo("Checking satisfiability...")
    solution = solver_instance.check()

    result = f"Satisfiable: {solution.satisfiable}\n"

    if solution.satisfiable is False:
        click.echo("UNSATISFIABLE: The theory has no valid models.")
        result += "No models exist.\n"
    else:
        if solution.satisfiable is True:
            click.echo("SATISFIABLE: The theory has valid models.")
        else:
            click.echo("UNKNOWN: Satisfiability could not be determined.")
        if not check_only:
            click.echo("Enumerating all models...")
            model_count = 0
            for model in solver_instance.models():
                result += f"\n=== Model {model_count + 1} ===\n"
                if model.ground_terms:
                    for fact in model.ground_terms:
                        result += f"{fact}\n"
                else:
                    result += "(empty model)\n"
                model_count += 1

            if model_count == 0:
                result += "No models generated (solver may not support model enumeration).\n"
            else:
                result += f"\nTotal models found: {model_count}\n"


    # Output results
    if output_file:
        with open(output_file, "w") as f:
            f.write(result)
        click.echo(f"Solution written to {output_file}")
    else:
        click.echo("\n" + "="*50)
        click.echo(result.rstrip())


@app.command()
def dump(
    input_files: List[Path] = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    output_format: str = typer.Option("yaml", "--output-format", "-t", help="Output format (fol, yaml, prolog, etc.)"),
    output_file: Optional[Path] = output_file_option,
    validate_types: bool = typer.Option(
        True, "--validate-types/--no-validate-types", help="Use mypy to validate types"
    ),
):
    """
    Parse and combine multiple input files, then export to specified format without solving.
    
    This command is useful for preprocessing, format conversion, and inspecting
    the combined logical theory before solving.
    
    Files can be Python (.py) or YAML (.yaml) format - format is auto-detected.

    Examples
    --------
    ```bash
    # Combine and export to first-order logic
    typedlogic dump theory.py facts.yaml -t fol -o combined.fol
    
    # Export to YAML format
    typedlogic dump axioms.py data.yaml -t yaml
    
    # Combine multiple files and view as Prolog
    typedlogic dump theory1.py theory2.py facts.yaml -t prolog
    ```

    """
    # Combine all input files into a single theory
    try:
        combined_theory = _combine_input_files(input_files, validate_types)
    except ValueError as e:
        click.echo(f"Error: {e}")
        raise typer.Exit(1)

    # Get compiler for output format
    try:
        compiler = get_compiler(output_format)
    except ValueError as e:
        click.echo(f"Error: {e}")
        raise typer.Exit(1)

    # Compile the combined theory
    try:
        result = compiler.compile(combined_theory)
    except Exception as e:
        click.echo(f"Error compiling theory: {e}")
        raise typer.Exit(1)

    # Output results
    if output_file:
        with open(output_file, "w") as f:
            f.write(result)
        click.echo(f"Combined theory exported to {output_file}")
    else:
        click.echo(result)


# DO NOT REMOVE THIS LINE
# added this for mkdocstrings to work
# see https://github.com/bruce-szalwinski/mkdocs-typer/issues/18
click_app = get_command(app)
click_app.name = "typedlogic"

if __name__ == "__main__":
    app()
