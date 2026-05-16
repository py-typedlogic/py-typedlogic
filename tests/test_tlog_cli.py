"""CLI tests for TLog parser/compiler integration."""

from pathlib import Path

import pytest
from typedlogic.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def check(condition: bool, message: str) -> None:
    """Fail the test if the condition is false."""
    if not condition:
        pytest.fail(message)


def test_convert_tlog_with_inferred_input_format(tmp_path: Path) -> None:
    """TLog is available through the generic convert command."""
    tlog_path = tmp_path / "family.tlog"
    tlog_path.write_text(
        """
        type PersonID: str.
        pred parent(parent: PersonID, child: PersonID).
        pred ancestor(ancestor: PersonID, descendant: PersonID).
        parent(Alice, Bob).
        ancestor(x, y) :- parent(x, y).
        """,
        encoding="utf-8",
    )

    prolog = runner.invoke(app, ["convert", str(tlog_path), "-t", "prolog"])
    check(prolog.exit_code == 0, prolog.stdout)
    check("ancestor(X, Y) :- parent(X, Y)." in prolog.stdout, prolog.stdout)

    tlog = runner.invoke(app, ["convert", str(tlog_path), "-t", "tlog"])
    check(tlog.exit_code == 0, tlog.stdout)
    check("pred parent(parent: PersonID, child: PersonID)." in tlog.stdout, tlog.stdout)
    check("all x, y | ancestor(x, y) :- parent(x, y)." in tlog.stdout, tlog.stdout)


def test_solve_tlog_with_selected_predicates_and_model_limit(tmp_path: Path) -> None:
    """The generic solve command can filter materialized predicates and limit model output."""
    pytest.importorskip("clingo")
    tlog_path = tmp_path / "worlds.tlog"
    tlog_path.write_text(
        """
        pred selected(option: str).
        pred hidden(option: str).
        selected("tea") | selected("coffee").
        hidden("noise").
        """,
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "solve",
            str(tlog_path),
            "--solver",
            "clingo",
            "--show",
            "selected",
            "--max-models",
            "1",
        ],
    )

    check(result.exit_code == 0, result.stdout)
    check("Satisfiable: True" in result.stdout, result.stdout)
    check("selected(" in result.stdout, result.stdout)
    check("hidden(" not in result.stdout, result.stdout)
    check("Total models shown: 1" in result.stdout, result.stdout)
