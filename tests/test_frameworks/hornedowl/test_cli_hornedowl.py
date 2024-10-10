import os
import tempfile
from pathlib import Path

import pytest

from tests.test_frameworks.hornedowl import HORNEDOWL_INPUT_DIR
from typedlogic.cli import app  # Import your Typer app
from typer.testing import CliRunner

from tests import OUTPUT_DIR
from typedlogic.integrations.frameworks.hornedowl.owl_parser import OWLParser

runner = CliRunner()

RO = HORNEDOWL_INPUT_DIR / "ro.ofn"

@pytest.mark.parametrize("input_file", [
        RO,
])
@pytest.mark.parametrize("output_format", [
    "fol",
    "prolog",
    "sexpr"
])
def test_convert_owl(input_file, output_format):
    stem = input_file.stem
    output_path = OUTPUT_DIR /  f"from-owl-{stem}.{output_format}"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    print(output_path)
    result = runner.invoke(app, ['convert', str(input_file), '--input-format', "owl", '--output-format', output_format, '-o', str(output_path)])
    if result.exit_code != 0:
        print(result.stdout)
    assert result.exit_code == 0

