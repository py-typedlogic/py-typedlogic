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

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, List, Optional

import click
import typer
from typer.main import get_command

from typedlogic.compilers.tlog_compiler import TLogCompiler
from typedlogic.datamodel import (
    And,
    Exists,
    NegationAsFailure,
    Not,
    Or,
    Sentence,
    SentenceGroup,
    SentenceGroupType,
    Term,
    Theory,
    Variable,
)
from typedlogic.registry import (
    all_compiler_classes,
    all_parser_classes,
    all_solver_classes,
    get_compiler,
    get_parser,
    get_solver,
)
from typedlogic.solver import Model, Solver
from typedlogic.transformations import clark_completion

app = typer.Typer()

input_format_option = typer.Option(
    None, "--input-format", "-f", help="Input format; inferred from file suffix if omitted"
)
output_format_option = typer.Option(None, "--output-format", "-t", help="Output format")

output_file_option = typer.Option(None, "--output-file", "-o", help="Output file path")

dump_program_option = typer.Option(
    False,
    "--dump-program",
    "--show-program",
    help="Print the solver-specific generated program before solving.",
)


class ProveTarget(str, Enum):
    """The kinds of proof obligations to run."""

    ALL = "all"
    GOALS = "goals"
    LEMMAS = "lemmas"


@dataclass(frozen=True)
class TestCaseSpec:
    """A quoted TLog test case extracted from a theory."""

    name: str
    givens: list[Sentence]
    expects: list[Sentence]


@dataclass(frozen=True)
class ProofObligation:
    """A goal or lemma that should be proved without being asserted."""

    kind: SentenceGroupType
    name: str
    sentence: Sentence


@dataclass
class ExpectationContext:
    """Cached solver state for evaluating a single test case."""

    solver: Solver
    _satisfiable: Optional[bool] = None
    _models: Optional[list[Model]] = None

    def satisfiable(self) -> Optional[bool]:
        """Return whether the test fixture is satisfiable."""
        if self._satisfiable is None:
            self._satisfiable = self.solver.check().satisfiable
        return self._satisfiable

    def models(self) -> list[Model]:
        """Return all models produced by the solver."""
        if self._models is None:
            self._models = list(self.solver.models())
        return self._models

    def prove(self, sentence: Sentence) -> Optional[bool]:
        """Prove a sentence using the solver, falling back to model entailment."""
        if _is_satisfiable_term(sentence):
            return self.satisfiable()
        if type(self.solver).prove is not Solver.prove:
            result = self.solver.prove(sentence)
            if result is not None:
                return result
        if isinstance(sentence, Exists) and isinstance(sentence.sentence, Term):
            return self._models_entail(sentence.sentence)
        if isinstance(sentence, (Term, Not)):
            return self._models_entail(sentence)
        if type(self.solver).prove is not Solver.prove:
            return None
        return self.solver.prove(sentence)

    def _models_entail(self, sentence: Sentence) -> bool:
        models = self.models()
        if not models:
            return False
        return all(_model_satisfies(model, sentence) for model in models)


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
    input_format: Optional[str] = input_format_option,
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
    parser = get_parser(input_format or _guess_format(theory_files[0]))
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
    if data_file.name.endswith(".catalog.yaml") or data_file.name.endswith(".catalog.yml"):
        return "catalog"
    if data_file.name.endswith(".tlog.md"):
        return "tlogmarkdown"

    suffix = data_file.suffix[1:]
    if suffix == "py":
        return "python"
    elif suffix in ["csv", "tsv", "xlsx", "xls", "tab"]:
        return "dataframe"
    return suffix


def _combine_input_files(
    input_files: List[Path],
    validate_types: bool = True,
    input_format: Optional[str] = None,
):
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
        file_format = input_format or _guess_format(input_file)
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
                if hasattr(parsed_result, "sentences") or hasattr(parsed_result, "predicate_definitions"):
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
                if hasattr(parsed_result, "sentences") or hasattr(parsed_result, "predicate_definitions"):
                    file_theory = parsed_result

                    # Merge sentences (axioms)
                    if hasattr(file_theory, "sentences") and file_theory.sentences:
                        if combined_theory.sentences is None:
                            combined_theory.sentences = []
                        combined_theory.sentences.extend(file_theory.sentences)

                    # Merge ground terms (facts)
                    if hasattr(file_theory, "ground_terms") and file_theory.ground_terms:
                        if combined_theory.ground_terms is None:
                            combined_theory.ground_terms = []
                        combined_theory.ground_terms.extend(file_theory.ground_terms)

                    # Merge predicate definitions
                    if hasattr(file_theory, "predicate_definitions") and file_theory.predicate_definitions:
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


def _parse_theory_file(theory_file: Path, input_format: Optional[str], validate_types: bool) -> Theory:
    """Parse one theory file, optionally validating Python inputs."""
    parser = get_parser(input_format or _guess_format(theory_file))
    if validate_types:
        errs = parser.validate(theory_file)
        if errs:
            for err in errs:
                click.echo(f"Validation error in {theory_file}: {err}")
            raise typer.Exit(1)
    theory = parser.parse(theory_file)
    if not isinstance(theory, Theory):
        raise click.ClickException(f"Expected a theory from {theory_file}, got {type(theory).__name__}")
    return theory


def _add_data_files(theory: Theory, data_files: Optional[List[Path]], data_input_format: Optional[str]) -> None:
    """Parse data files and add their ground terms to a theory."""
    if not data_files:
        return
    if theory.ground_terms is None:
        theory.ground_terms = []
    for data_file in data_files:
        data_parser = get_parser(data_input_format or _guess_format(data_file))
        terms = data_parser.parse_ground_terms(data_file)
        theory.ground_terms.extend(terms)


def _get_solver_instance(solver_name: str) -> Solver:
    """Create a solver instance, presenting registry errors as CLI errors."""
    try:
        return get_solver(solver_name)
    except ValueError as e:
        click.echo(f"Error: {e}")
        raise typer.Exit(1) from None


def _test_cases(theory: Theory) -> list[TestCaseSpec]:
    """Extract quoted test_case statements from a theory."""
    cases: list[TestCaseSpec] = []
    for group in theory.sentence_groups:
        if group.group_type != SentenceGroupType.TEST:
            continue
        for sentence in group.sentences or []:
            if not isinstance(sentence, Term) or sentence.predicate != "test_case":
                raise click.ClickException(f"Test group {group.name} must contain test_case(...), got {sentence}")
            cases.append(_test_case_from_term(group, sentence))
    return cases


def _test_case_from_term(group: SentenceGroup, term: Term) -> TestCaseSpec:
    """Convert a test_case(...) term into a runnable test case."""
    values = list(term.values)
    if not values:
        raise click.ClickException(f"Test group {group.name} has no test case name")
    name = str(values[0])
    givens: list[Sentence] = []
    expects: list[Sentence] = []
    for value in values[1:]:
        if not isinstance(value, Term):
            raise click.ClickException(f"Test case {name} expects given(...) or expect(...), got {value}")
        if value.predicate == "given":
            givens.extend(_quoted_arguments(name, value))
        elif value.predicate == "expect":
            expects.extend(_quoted_arguments(name, value))
        else:
            raise click.ClickException(f"Test case {name} expects given(...) or expect(...), got {value}")
    if not expects:
        raise click.ClickException(f"Test case {name} must include at least one expect(that(...))")
    return TestCaseSpec(name=name, givens=givens, expects=expects)


def _quoted_arguments(test_name: str, term: Term) -> list[Sentence]:
    """Unwrap every that(...) argument in a given(...) or expect(...) term."""
    if not term.values:
        raise click.ClickException(f"{term.predicate}(...) in test case {test_name} must contain that(...)")
    return [_unwrap_that(test_name, value) for value in term.values]


def _unwrap_that(context_name: str, value: Any) -> Sentence:
    """Return the sentence quoted by that(...)."""
    if not isinstance(value, Term) or value.predicate != "that" or len(value.values) != 1:
        raise click.ClickException(f"{context_name} expects that(sentence), got {value}")
    quoted = value.values[0]
    if not isinstance(quoted, Sentence):
        raise click.ClickException(f"{context_name} expects a quoted sentence, got {quoted}")
    return quoted


def _proof_obligations(theory: Theory, target: ProveTarget) -> list[ProofObligation]:
    """Extract goal and lemma obligations from a theory."""
    obligations: list[ProofObligation] = []
    include_goals = target in {ProveTarget.ALL, ProveTarget.GOALS}
    include_lemmas = target in {ProveTarget.ALL, ProveTarget.LEMMAS}
    for group in theory.sentence_groups:
        if group.group_type == SentenceGroupType.GOAL and include_goals:
            obligations.extend(_obligations_from_group(group))
        if group.group_type == SentenceGroupType.LEMMA and include_lemmas:
            obligations.extend(_obligations_from_group(group))
    return obligations


def _obligations_from_group(group: SentenceGroup) -> list[ProofObligation]:
    """Create proof obligations for each sentence in a goal or lemma group."""
    if group.group_type not in {SentenceGroupType.GOAL, SentenceGroupType.LEMMA}:
        return []
    return [
        ProofObligation(kind=group.group_type, name=group.name, sentence=sentence) for sentence in group.sentences or []
    ]


def _selected_by_name(name: str, selected_names: Optional[List[str]]) -> bool:
    """Return whether a named item should run under repeated name filters."""
    return not selected_names or name in selected_names


def _evaluate_expectation(context: ExpectationContext, sentence: Sentence) -> Optional[bool]:
    """Evaluate a quoted expectation sentence."""
    if isinstance(sentence, And):
        results = [_evaluate_expectation(context, operand) for operand in sentence.operands]
        if any(result is False for result in results):
            return False
        if any(result is None for result in results):
            return None
        return True
    if isinstance(sentence, Or):
        results = [_evaluate_expectation(context, operand) for operand in sentence.operands]
        if any(result is True for result in results):
            return True
        if any(result is None for result in results):
            return None
        return False
    if isinstance(sentence, NegationAsFailure):
        result = _evaluate_expectation(context, sentence.negated)
        if result is None:
            return None
        return not result
    if isinstance(sentence, Not):
        result = _evaluate_expectation(context, sentence.negated)
        if result is None:
            return None
        return not result
    return context.prove(sentence)


def _model_satisfies(model: Model, sentence: Sentence) -> bool:
    """Return whether one materialized model contains a sentence."""
    if isinstance(sentence, Term):
        return _model_contains_term(model, sentence)
    if isinstance(sentence, Not):
        return not _model_satisfies(model, sentence.negated)
    return False


def _model_contains_term(model: Model, sentence: Term) -> bool:
    """Return whether one materialized model contains a term."""
    sentence_values = sentence.values
    has_vars = any(isinstance(value, Variable) for value in sentence_values)
    for term in model.iter_retrieve(sentence.predicate):
        if term == sentence:
            return True
        if has_vars and _term_matches_with_variables(term, sentence_values):
            return True
    return False


def _term_matches_with_variables(term: Term, sentence_values: tuple[Any, ...]) -> bool:
    """Return whether a ground term matches expected values containing variables."""
    if len(term.values) != len(sentence_values):
        return False
    bindings: dict[str, Any] = {}
    for expected, actual in zip(sentence_values, term.values, strict=True):
        if not isinstance(expected, Variable):
            if expected != actual:
                return False
            continue
        if expected.name in bindings:
            if bindings[expected.name] != actual:
                return False
            continue
        bindings[expected.name] = actual
    return True


def _is_satisfiable_term(sentence: Sentence) -> bool:
    """Return whether a sentence is the built-in satisfiable() expectation."""
    return isinstance(sentence, Term) and sentence.predicate == "satisfiable" and len(sentence.values) == 0


def _format_sentence(sentence: Sentence) -> str:
    """Format a sentence in TLog syntax for CLI output."""
    compiled = TLogCompiler().compile_sentence(sentence).strip()
    return compiled[:-1] if compiled.endswith(".") else compiled


def _status(result: Optional[bool]) -> str:
    """Format a tri-state proof or expectation result."""
    if result is True:
        return "PASS"
    if result is False:
        return "FAIL"
    return "UNKNOWN"


def _run_test_cases(
    theory: Theory,
    cases: list[TestCaseSpec],
    solver_name: str,
    dump_program: bool,
) -> tuple[int, int]:
    """Run selected test cases and return failed and unknown counts."""
    failed = 0
    unknown = 0
    for case in cases:
        solver_instance = _get_solver_instance(solver_name)
        solver_instance.add(theory)
        for given in case.givens:
            solver_instance.add(given)

        if dump_program:
            try:
                program = solver_instance.dump()
            except NotImplementedError:
                click.echo(f"Error: Solver '{solver_name}' does not support dumping generated programs.")
                raise typer.Exit(1) from None
            click.echo(f"=== Program: {case.name} ===")
            click.echo(program.rstrip())

        context = ExpectationContext(solver_instance)
        results = [_evaluate_expectation(context, expected) for expected in case.expects]
        if any(result is False for result in results):
            case_result: Optional[bool] = False
            failed += 1
        elif any(result is None for result in results):
            case_result = None
            unknown += 1
        else:
            case_result = True

        click.echo(f"{_status(case_result)} {case.name}")
        if case_result is not True or len(case.expects) > 1:
            for expected, result in zip(case.expects, results, strict=True):
                click.echo(f"  {_status(result)} expect {_format_sentence(expected)}")

    if cases:
        click.echo(f"{len(cases)} test case(s), {failed} failed, {unknown} unknown")
    return failed, unknown


def _run_proof_obligations(
    theory: Theory,
    obligations: list[ProofObligation],
    solver_name: str,
    dump_program: bool,
) -> tuple[int, int]:
    """Run selected proof obligations and return failed and unknown counts."""
    if not obligations:
        return 0, 0

    solver_instance = _get_solver_instance(solver_name)
    solver_instance.add(theory)

    if dump_program:
        try:
            program = solver_instance.dump()
        except NotImplementedError:
            click.echo(f"Error: Solver '{solver_name}' does not support dumping generated programs.")
            raise typer.Exit(1) from None
        click.echo(program.rstrip())

    context = ExpectationContext(solver_instance)
    failed = 0
    unknown = 0
    for obligation in obligations:
        result = context.prove(obligation.sentence)
        if result is False:
            failed += 1
        if result is None:
            unknown += 1
        click.echo(
            f"{_status(result)} {obligation.kind.value} {obligation.name}: {_format_sentence(obligation.sentence)}"
        )

    click.echo(f"{len(obligations)} obligation(s), {failed} failed, {unknown} unknown")
    return failed, unknown


@app.command()
def test(
    theory_file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    solver: str = typer.Option("souffle", "--solver", "-s", help="Solver to use (z3, souffle, clingo, etc.)"),
    proof_target: ProveTarget = typer.Option(
        ProveTarget.ALL,
        "--target",
        help="Proof obligations to run after test cases: all, goals, or lemmas.",
    ),
    validate_types: bool = typer.Option(
        True, "--validate-types/--no-validate-types", help="Use mypy to validate types"
    ),
    input_format: Optional[str] = input_format_option,
    data_input_format: Optional[str] = typer.Option(None, "--data-input-format", "-d", help="Format for ground terms"),
    selected_tests: Optional[List[str]] = typer.Option(
        None,
        "--test",
        help="Only run a named test case. Repeat for multiple tests.",
    ),
    selected_names: Optional[List[str]] = typer.Option(
        None,
        "--name",
        help="Only prove obligations from a named goal or lemma group. Repeat for multiple names.",
    ),
    run_proofs: bool = typer.Option(
        True,
        "--proofs/--no-proofs",
        help="Also prove goal and lemma obligations.",
    ),
    dump_program: bool = dump_program_option,
    data_files: Annotated[Optional[List[Path]], typer.Argument()] = None,
):
    """
    Run quoted test_case(...) declarations and prove goals and lemmas embedded in a theory.

    Tests are off by default for `solve`. This command opts into test metadata:
    each `given(that(...))` is temporarily asserted, and each `expect(that(...))`
    is checked against the resulting solver state. Goal and lemma metadata is
    also proved against the base theory unless `--no-proofs` is used.
    """
    theory = _parse_theory_file(theory_file, input_format, validate_types)
    _add_data_files(theory, data_files, data_input_format)
    cases = [case for case in _test_cases(theory) if _selected_by_name(case.name, selected_tests)]
    obligations = []
    if run_proofs:
        obligations = [
            obligation
            for obligation in _proof_obligations(theory, proof_target)
            if _selected_by_name(obligation.name, selected_names)
        ]
    if selected_tests and not cases:
        click.echo("No matching test cases found.")
        raise typer.Exit(1)
    if run_proofs and selected_names and not obligations:
        click.echo("No matching proof obligations found.")
        raise typer.Exit(1)
    if not cases and not obligations:
        click.echo("No matching test cases or proof obligations found.")
        raise typer.Exit(1)

    test_failed, test_unknown = _run_test_cases(theory, cases, solver or "souffle", dump_program)
    proof_failed, proof_unknown = _run_proof_obligations(theory, obligations, solver or "souffle", dump_program)
    if test_failed or test_unknown or proof_failed or proof_unknown:
        raise typer.Exit(1)


@app.command()
def prove(
    theory_file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    solver: str = typer.Option("z3", "--solver", "-s", help="Solver to use (z3, prover9, clingo, etc.)"),
    target: ProveTarget = typer.Option(
        ProveTarget.ALL,
        "--target",
        help="Proof obligations to run: all, goals, or lemmas.",
    ),
    validate_types: bool = typer.Option(
        True, "--validate-types/--no-validate-types", help="Use mypy to validate types"
    ),
    input_format: Optional[str] = input_format_option,
    data_input_format: Optional[str] = typer.Option(None, "--data-input-format", "-d", help="Format for ground terms"),
    selected_names: Optional[List[str]] = typer.Option(
        None,
        "--name",
        help="Only prove obligations from a named goal or lemma group. Repeat for multiple names.",
    ),
    use_clark_completion: bool = typer.Option(
        False,
        "--clark-completion/--no-clark-completion",
        help="Apply Clark completion so negation-as-failure rules get a classical rendering "
        "(for classical solvers such as z3 or prover9).",
    ),
    dump_program: bool = dump_program_option,
    data_files: Annotated[Optional[List[Path]], typer.Argument()] = None,
):
    """
    Prove goal and lemma obligations embedded in a theory.

    Goals and lemmas are not asserted as axioms. This command loads the base
    theory and asks the selected solver to prove each quoted obligation.
    """
    theory = _parse_theory_file(theory_file, input_format, validate_types)
    _add_data_files(theory, data_files, data_input_format)
    if use_clark_completion:
        theory = clark_completion(theory)
    obligations = [
        obligation
        for obligation in _proof_obligations(theory, target)
        if _selected_by_name(obligation.name, selected_names)
    ]
    if not obligations:
        click.echo("No matching proof obligations found.")
        raise typer.Exit(1)

    failed, unknown = _run_proof_obligations(theory, obligations, solver or "z3", dump_program)
    if failed or unknown:
        raise typer.Exit(1)


@app.command()
def solve(
    theory_file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    solver: str = typer.Option("souffle", "--solver", "-s", help="Solver to use (z3, souffle, clingo, etc.)"),
    check_only: bool = typer.Option(
        False, "--check-only", "-c", help="Check satisfiability only, do not enumerate models"
    ),
    validate_types: bool = typer.Option(
        True, "--validate-types/--no-validate-types", help="Use mypy to validate types"
    ),
    input_format: Optional[str] = input_format_option,
    data_input_format: str = typer.Option(None, "--data-input-format", "-d", help="Format for ground terms"),
    output_format: str = output_format_option,
    output_file: Optional[Path] = output_file_option,
    show_predicates: Optional[List[str]] = typer.Option(
        None,
        "--show",
        "--predicate",
        help="Only show materialized ground terms for these predicates. Repeat for multiple predicates.",
    ),
    max_models: Optional[int] = typer.Option(None, "--max-models", help="Stop after showing this many models"),
    dump_program: bool = dump_program_option,
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
    combined_theory = _parse_theory_file(theory_file, input_format, validate_types)

    # Parse data files and add ground terms
    _add_data_files(combined_theory, data_files, data_input_format)

    # Initialize solver
    solver_instance = _get_solver_instance(solver or "souffle")

    # Load theory into solver
    solver_instance.add(combined_theory)

    if dump_program:
        try:
            program = solver_instance.dump()
        except NotImplementedError:
            click.echo(f"Error: Solver '{solver}' does not support dumping generated programs.")
            raise typer.Exit(1) from None
        click.echo(program.rstrip())

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
                facts = model.ground_terms
                if show_predicates:
                    facts = [fact for fact in facts if str(fact.predicate) in show_predicates]
                if facts:
                    for fact in facts:
                        result += f"{fact}\n"
                else:
                    result += "(empty model)\n"
                model_count += 1
                if max_models is not None and model_count >= max_models:
                    break

            if model_count == 0:
                result += "No models generated (solver may not support model enumeration).\n"
            else:
                result += f"\nTotal models shown: {model_count}\n"

    # Output results
    if output_file:
        with open(output_file, "w") as f:
            f.write(result)
        click.echo(f"Solution written to {output_file}")
    else:
        click.echo("\n" + "=" * 50)
        click.echo(result.rstrip())


@app.command()
def dump(
    input_files: List[Path] = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    input_format: Optional[str] = input_format_option,
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
        combined_theory = _combine_input_files(input_files, validate_types, input_format)
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
