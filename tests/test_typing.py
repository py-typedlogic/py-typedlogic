import os
import tempfile
from pathlib import Path

import pytest
from mypy import api
from typedlogic.parsers.pyparser import PythonParser

# Template code with named placeholders
test_code = """
from typedlogic import gen2

for x, y in gen2({t1}, {t2}):
    print(x + y)  # This may trigger a mypy error depending on the types
"""


@pytest.fixture
def temp_file_with_test_code():
    def _create_temp_file(t1, t2):
        # Fill the template with the provided named arguments
        filled_code = test_code.format(
            t1=t1,
            t2=t2,
        )

        # Write the code to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".py") as temp_file:
            temp_file.write(filled_code.encode('utf-8'))
            temp_file_path = temp_file.name

        return temp_file_path

    yield _create_temp_file

    # No need to clean up here; that can be done in the test function itself.


@pytest.mark.parametrize(
    "type1, type2, valid",
    [
        ("str", "str", True),
        ("str", "int", False),
        ("int", "int", True),
        ("float", "int", True),
    ]
)
@pytest.mark.parametrize("use_parser", [True, False])
def test_typing_combinations(temp_file_with_test_code, use_parser, type1, type2, valid):
    # Create the temporary file with the filled-in code
    temp_file_path = temp_file_with_test_code(type1, type2)

    if use_parser:
        pp = PythonParser()
        errs = pp.validate(Path(temp_file_path))
        if valid:
            assert not errs
        else:
            assert errs
        return
    try:
        # Run mypy via its Python API
        result = api.run([temp_file_path])

        # The first element in the result tuple contains stdout, the second contains stderr,
        # and the third contains the return code
        stdout, stderr, exit_code = result

        # Check that mypy caught the errors if the case is supposed to be invalid
        if valid:
            assert "error:" not in stdout
            assert exit_code == 0  # Ensure mypy returned a success exit code
        else:
            assert "error:" in stdout
            assert exit_code != 0  # Ensure mypy returned a failure exit code
    finally:
        # Clean up the temporary file after the test
        os.remove(temp_file_path)
