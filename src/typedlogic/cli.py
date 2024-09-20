"""
Command-line interface definitions using typer.
"""
from pathlib import Path
from typing import List, Optional

import typer

from typedlogic.parsers.pyparser.python_parser import PythonParser
from typedlogic.registry import get_compiler, get_solver

app = typer.Typer()



@app.command()
def convert(
        input_files: List[Path] = typer.Argument(..., exists=True, dir_okay=False, readable=True),
        output_format: str = typer.Option(None, "--output-format", "-t", help="Output format"),
        output_file: Optional[Path] = typer.Option(None, "--output-file", "-o", help="Output file path")
):
    """
    Convert from one logic form to another.
    """
    parser = PythonParser()
    theory = parser.parse(input_files[0])
    if len(input_files) > 1:
        for input_file in input_files[1:]:
            facts_theory = parser.parse(input_file)
            for s in facts_theory.sentences:
                theory.add(s)

    compiler = get_compiler(output_format or "z3sexpr")
    result = compiler.compile(theory)

    if output_file:
        with open(output_file, 'w') as f:
            f.write(result)
        typer.echo(f"Conversion result written to {output_file}")
    else:
        typer.echo(result)


@app.command()
def solve(
        input_file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
        solver: str = typer.Option(None, help="Solver to use"),
        output_file: Optional[Path] = typer.Option(None, "--output-file", "-o", help="Output file path for the solution")
):
    """
    Solve using the specified solver.
    """
    parser = PythonParser()
    theory = parser.parse(input_file)
    solver_instance = get_solver(solver or "souffle")

    solver_instance.add(theory)
    solution = solver_instance.check()

    result = f"Satisfiable: {solution.satisfiable}\n"
    if solution.satisfiable:
        model = solver_instance.model()
        result += "Model:\n"
        for fact in model.ground_terms:
            result += f"{fact}\n"

    if output_file:
        with open(output_file, 'w') as f:
            f.write(result)
        typer.echo(f"Solution written to {output_file}")
    else:
        typer.echo(result)


if __name__ == "__main__":
    app()
