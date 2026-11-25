"""Repository-wide pytest configuration (applies to doctest runs over ``src`` as well as ``tests``)."""

import shutil
from doctest import DocTest
from typing import Optional

import pytest

#: Doctests that invoke an external solver executable, keyed by a path fragment of their module.
DOCTEST_EXECUTABLES = {
    "integrations/frameworks/owldl/reasoner.py": "souffle",
    "integrations/frameworks/rdflib/rdf_parser.py": "souffle",
    "integrations/solvers/prover9/prover9_solver.py": "prover9",
}


def missing_doctest_executable(nodeid: str) -> Optional[str]:
    """
    Name the external executable a doctest needs, if it is not installed.

        >>> missing_doctest_executable("src/typedlogic/datamodel.py::typedlogic.datamodel.Term") is None
        True

    :param nodeid: the pytest node id of the doctest
    :return: the missing executable, or None if the doctest can run
    """
    for fragment, executable in DOCTEST_EXECUTABLES.items():
        if fragment in nodeid and shutil.which(executable) is None:
            return executable
    return None


def pytest_collection_modifyitems(config, items):
    """Skip doctests whose external solver executable is unavailable, as tests/conftest.py does for tests."""
    for item in items:
        if not isinstance(getattr(item, "dtest", None), DocTest):
            continue
        executable = missing_doctest_executable(item.nodeid)
        if executable:
            item.add_marker(pytest.mark.skip(reason=f"{executable} executable not found"))
