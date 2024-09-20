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

@pytest.mark.parametrize("output_format", ["z3sexpr", "z3functional", "prolog", "souffle", "tptp"])
@pytest.mark.parametrize("input_file", ["animals", "mortals", "paths", "numbers"])
def test_convert_multiple(output_format, input_file):
    input_file = Path(__file__).parent / f"theorems/{input_file}.py"
    output_path = OUTPUT_DIR / f"theorems/{input_file.stem}.{output_format}"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = runner.invoke(app, ['convert', str(input_file), '--output-format', output_format, '--output-file', str(output_path)])
    if result.exit_code != 0:
        print(result.stdout)
    assert result.exit_code == 0
