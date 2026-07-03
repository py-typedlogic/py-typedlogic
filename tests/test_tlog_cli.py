"""CLI tests for TLog parser/compiler integration."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from typedlogic.cli import app

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


def test_solve_tlog_can_dump_generated_clingo_program(tmp_path: Path) -> None:
    """The solve command can print the generated solver program before solving."""
    pytest.importorskip("clingo")
    tlog_path = tmp_path / "constraints.tlog"
    tlog_path.write_text(
        """
        pred person(id: str).
        pred has_name(id: str).
        :- person(x), not has_name(x).
        person("p1").
        has_name("p1").
        test_case("person_has_name", given(that(person("p1"))), expect(that(has_name("p1")))).
        """,
        encoding="utf-8",
    )

    result = runner.invoke(app, ["solve", str(tlog_path), "--solver", "clingo", "--dump-program"])

    check(result.exit_code == 0, result.stdout)
    check(":- person(X), not has_name(X)." in result.stdout, result.stdout)
    check('person("p1").' in result.stdout, result.stdout)
    check('has_name("p1").' in result.stdout, result.stdout)
    check("test_case" not in result.stdout, result.stdout)
    check("given(" not in result.stdout, result.stdout)
    check("expect(" not in result.stdout, result.stdout)
    check("Checking satisfiability" in result.stdout, result.stdout)
    check("Satisfiable: True" in result.stdout, result.stdout)


def test_tlog_test_command_runs_quoted_test_cases(tmp_path: Path) -> None:
    """The test command runs quoted test_case metadata without asserting it globally."""
    pytest.importorskip("clingo")
    tlog_path = tmp_path / "mortality.tlog"
    tlog_path.write_text(
        """
        pred human(name: str).
        pred mortal(name: str).
        mortal(x) :- human(x).

        test_case(
          "socrates_mortality",
          given(that(human("socrates"))),
          expect(that(satisfiable() & mortal("socrates") & not philosopher("socrates") & ~student("socrates")))
        ).
        """,
        encoding="utf-8",
    )

    result = runner.invoke(app, ["test", str(tlog_path), "--solver", "clingo"])

    check(result.exit_code == 0, result.stdout)
    check("PASS socrates_mortality" in result.stdout, result.stdout)
    check("1 test case(s), 0 failed, 0 unknown" in result.stdout, result.stdout)


def test_tlog_test_command_fails_when_expectation_is_not_entailed(tmp_path: Path) -> None:
    """The test command exits non-zero when an expectation fails."""
    pytest.importorskip("clingo")
    tlog_path = tmp_path / "mortality.tlog"
    tlog_path.write_text(
        """
        pred human(name: str).
        pred mortal(name: str).

        test_case(
          "plato_mortality",
          given(that(human("plato"))),
          expect(that(mortal("plato")))
        ).
        """,
        encoding="utf-8",
    )

    result = runner.invoke(app, ["test", str(tlog_path), "--solver", "clingo"])

    check(result.exit_code == 1, result.stdout)
    check("FAIL plato_mortality" in result.stdout, result.stdout)
    check("FAIL expect mortal('plato')" in result.stdout, result.stdout)


def test_tlog_prove_command_proves_quoted_lemmas(tmp_path: Path) -> None:
    """The prove command treats lemmas as proof obligations, not axioms."""
    pytest.importorskip("z3")
    tlog_path = tmp_path / "mortality.tlog"
    tlog_path.write_text(
        """
        pred human(name: str).
        pred mortal(name: str).
        human("socrates").
        all x | mortal(x) :- human(x).

        lemma("socrates_is_mortal", that(mortal("socrates"))).
        """,
        encoding="utf-8",
    )

    result = runner.invoke(app, ["prove", str(tlog_path), "--solver", "z3", "--target", "lemmas"])

    check(result.exit_code == 0, result.stdout)
    check("PASS lemma socrates_is_mortal: mortal('socrates')" in result.stdout, result.stdout)
    check("1 obligation(s), 0 failed, 0 unknown" in result.stdout, result.stdout)


def test_tlog_prove_command_proves_negative_lemmas_with_model_fallback(tmp_path: Path) -> None:
    """The prove command can use model entailment for negative proof obligations."""
    pytest.importorskip("clingo")
    tlog_path = tmp_path / "mortality.tlog"
    tlog_path.write_text(
        """
        pred human(name: str).
        human("socrates").

        lemma("socrates_is_not_philosopher", that(~philosopher("socrates"))).
        """,
        encoding="utf-8",
    )

    result = runner.invoke(app, ["prove", str(tlog_path), "--solver", "clingo", "--target", "lemmas"])

    check(result.exit_code == 0, result.stdout)
    check("PASS lemma socrates_is_not_philosopher: ~philosopher('socrates')" in result.stdout, result.stdout)
    check("1 obligation(s), 0 failed, 0 unknown" in result.stdout, result.stdout)
