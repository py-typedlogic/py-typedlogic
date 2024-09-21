import os
import tempfile
from pathlib import Path

import pytest
from typedlogic.cli import app  # Import your Typer app
from typer.testing import CliRunner

from tests import OUTPUT_DIR

runner = CliRunner()

@pytest.fixture
def sample_input_file():
    content = """
from dataclasses import dataclass
from typedlogic import Fact, axiom

@dataclass
class Person(Fact):
    name: str

@dataclass
class Mortal(Fact):
    name: str
    
@axiom
def all_persons_are_mortal(i: str):
    if Person(i):
        assert Mortal(i)
    """
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as temp:
        temp.write(content)
    yield temp.name
    os.unlink(temp.name)

def test_convert_command(sample_input_file):
    result = runner.invoke(app, ['convert', sample_input_file, '--output-format', 'z3sexpr'])
    assert result.exit_code == 0
    assert "Person" in result.stdout


@pytest.mark.parametrize("module", [
    "tests.theorems.animals",
    "tests.theorems.defined_types_example",
    "tests.theorems.import_test.ext",
    "tests.theorems.mortals",
    "tests.theorems.numbers",
    "tests.theorems.optional_example",
    "tests.theorems.paths",
    "tests.theorems.paths_with_distance",
    "tests.theorems.simple_contradiction",
    "tests.theorems.types_example",
])
@pytest.mark.parametrize("output_formats", [
    ["sexpr"],
    ["yaml", "yaml", "sexpr"],
    ["prolog"],
    ["tptp"],
    ["souffle"],
])
def test_convert_command_multiple(module, output_formats):
    relative_location = f"{module.replace('.', '/')}.py"
    original_path = Path(__file__).parent.parent / relative_location
    input_path = OUTPUT_DIR / relative_location
    # copy file from original_path to input_path
    input_path.parent.mkdir(parents=True, exist_ok=True)
    with open(original_path, 'r') as f:
        with open(input_path, 'w') as g:
            g.write(f.read())
    input_format = "python"
    n = 0
    for output_format in output_formats:
        n += 1
        output_path = OUTPUT_DIR /  f"{input_path}.{output_format}"
        print(f"{n} {input_format} -> {output_format} :: {input_path} -> {output_path}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result = runner.invoke(app, ['convert', str(input_path), '--input-format', input_format, '--output-format', output_format, '-o', str(output_path)])
        if result.exit_code != 0:
            print(result.stdout)
        assert result.exit_code == 0
        input_format = output_format
        input_path = output_path



def test_convert_command_with_output_file(sample_input_file):
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as temp_out:
        result = runner.invoke(app, ['convert', sample_input_file, '--output-format', 'z3sexpr', '--output-file', temp_out.name])
        assert result.exit_code == 0
        assert "Conversion result written to" in result.stdout
        with open(temp_out.name, 'r') as f:
            content = f.read()
            assert "Person" in content
    os.unlink(temp_out.name)

@pytest.mark.parametrize("solver", ["z3", "clingo", "souffle", "snakelog"])
def test_solve_command(sample_input_file, solver):
    result = runner.invoke(app, ['solve', sample_input_file, '--solver', solver])
    if result.exit_code != 0:
        print(result.stdout)
    assert result.exit_code == 0
    assert "Satisfiable:" in result.stdout

def test_solve_command_with_output_file(sample_input_file):
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as temp_out:
        result = runner.invoke(app, ['solve', sample_input_file, '--solver', 'z3', '--output-file', temp_out.name])
        assert result.exit_code == 0
        assert "Solution written to" in result.stdout
        with open(temp_out.name, 'r') as f:
            content = f.read()
            assert "Satisfiable:" in content
    os.unlink(temp_out.name)



@pytest.mark.parametrize("theory,data_files,solver_class,expected",
    [("paths",
      ["Link.01.yaml"],
      "clingo",
      None),
     ("paths_with_distance",
      ["Link.01.yaml"],
      "clingo",
      None),
])
def test_solve_multiple(theory, data_files, solver_class, expected):
    input_file = Path(__file__).parent / f"theorems/{theory}.py"
    output_path = OUTPUT_DIR / f"theorems/{input_file.stem}.solver.{solver_class}.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data_files_input = [str(Path(__file__).parent / f"theorems/{theory}_data" / f) for f in data_files]
    print(data_files_input)
    result = runner.invoke(app, ['solve', str(input_file), '--output-file', str(output_path)] + data_files_input)
    if result.exit_code != 0:
        print(result.stdout)
    assert result.exit_code == 0
    # TODO: test actual output
