"""Tests for the ergonomic TypedLogic text parser."""

from pathlib import Path

import pytest

from typedlogic import Exists, Forall, Iff, Implies, NegationAsFailure, Not, Or, Term, Variable
from typedlogic.compilers.prolog_compiler import PrologCompiler
from typedlogic.compilers.tlog_compiler import TLogCompiler
from typedlogic.integrations.solvers.souffle.souffle_compiler import SouffleCompiler
from typedlogic.parsers.tlog_parser import TLogMarkdownParser, TLogParser
from typedlogic.registry import get_compiler, get_parser


def check(condition: bool, message: str) -> None:
    """Fail the test if the condition is false."""
    if not condition:
        pytest.fail(message)


def parse_one(source: str):
    """Parse source and return its only sentence."""
    theory = TLogParser().parse(source)
    check(len(theory.sentences) == 1, f"Expected one sentence, got {theory.sentences}")
    return theory.sentences[0]


def test_parse_type_and_predicate_declarations() -> None:
    """Type and predicate declarations populate the Theory metadata."""
    theory = TLogParser().parse(
        """
        type PointerID: str.
        type ElementID.
        pred PointerType(id: PointerID, element: ElementID).
        pred edge/2.
        pred Pred/1.
        """
    )

    check(theory.type_definitions == {"PointerID": "str", "ElementID": "str"}, str(theory.type_definitions))
    check(theory.predicate_definitions[0].predicate == "PointerType", str(theory.predicate_definitions))
    check(theory.predicate_definitions[0].arguments == {"id": "PointerID", "element": "ElementID"}, "bad args")
    check(theory.predicate_definitions[1].predicate == "edge", str(theory.predicate_definitions))
    check(theory.predicate_definitions[1].arguments == {"arg0": "str", "arg1": "str"}, "bad arity args")
    check(theory.predicate_definitions[2].predicate == "Pred", str(theory.predicate_definitions))


def test_parse_case_preserving_facts_with_quoted_constants() -> None:
    """Predicate case is preserved and quoted bare names are constants."""
    theory = TLogParser().parse(
        """
        Pred("Alice").
        pred("Alice").
        knows(Alice, Bob).
        """
    )

    check(
        theory.sentences == [Term("Pred", "Alice"), Term("pred", "Alice"), Term("knows", "Alice", "Bob")],
        repr(theory.sentences),
    )


def test_explicit_typed_forall_uses_declared_variable_names_without_case_assumptions() -> None:
    """Explicit quantifiers allow lowercase or uppercase variables with optional domains."""
    sentence = parse_one("all i: PointerID, C: ElementID | pointer_type(i, C) -> instance(i).")

    check(isinstance(sentence, Forall), repr(sentence))
    check([v.name for v in sentence.variables] == ["i", "C"], repr(sentence.variables))
    check([v.domain for v in sentence.variables] == ["PointerID", "ElementID"], repr(sentence.variables))
    check(repr(sentence.sentence) == "Implies(pointer_type(?i, ?C), instance(?i))", repr(sentence.sentence))


def test_implicit_universal_variables_are_not_case_based() -> None:
    """Unquantified rule variables are inferred from rule context, regardless of case."""
    sentence = parse_one("ancestor(x, Y) :- parent(x, z) & ancestor(z, Y).")

    check(isinstance(sentence, Forall), repr(sentence))
    check([v.name for v in sentence.variables] == ["x", "z", "Y"], repr(sentence.variables))
    check("ancestor(?x, ?Y)" in repr(sentence.sentence), repr(sentence.sentence))


def test_comma_is_body_conjunction_without_stealing_term_argument_commas() -> None:
    """Comma can be used as Prolog-style conjunction while predicate calls still parse multiple arguments."""
    theory = TLogParser().parse(
        """
        pair(Alice, Bob).
        ancestor(x, Y) :- parent(x, z), ancestor(z, Y).
        """
    )

    check(theory.sentences[0] == Term("pair", "Alice", "Bob"), repr(theory.sentences[0]))
    sentence = theory.sentences[1]
    check(isinstance(sentence, Forall), repr(sentence))
    check([v.name for v in sentence.variables] == ["x", "z", "Y"], repr(sentence.variables))
    check("parent(?x, ?z)" in repr(sentence.sentence), repr(sentence.sentence))


def test_rule_direction_variants_and_iff() -> None:
    """Rules can be written in either direction, and equivalence has explicit syntax."""
    theory = TLogParser().parse(
        """
        known(i) <- instance(i).
        instance(i) => known(i).
        all x | same(x) <-> equivalent(x).
        """
    )

    left_arrow = theory.sentences[0]
    right_arrow = theory.sentences[1]
    iff = theory.sentences[2]
    check(repr(left_arrow.sentence) == "Implies(instance(?i), known(?i))", repr(left_arrow))
    check(repr(right_arrow.sentence) == "Implies(instance(?i), known(?i))", repr(right_arrow))
    check(isinstance(iff, Forall), repr(iff))
    check(isinstance(iff.sentence, Iff), repr(iff.sentence))


def test_exists_quantifier() -> None:
    """Existential quantifiers are explicit and do not depend on variable casing."""
    sentence = parse_one("some witness | observed(witness).")

    check(isinstance(sentence, Exists), repr(sentence))
    check([v.name for v in sentence.variables] == ["witness"], repr(sentence.variables))
    check(repr(sentence.sentence) == "observed(?witness)", repr(sentence.sentence))


def test_unicode_quantifier_symbols() -> None:
    """Classic universal and existential quantifier symbols are accepted aliases."""
    theory = TLogParser().parse(
        """
        ∀ i: PointerID, C: ElementID | pointer_type(i, C) -> instance(i).
        ∃ witness | observed(witness).
        """
    )

    universal = theory.sentences[0]
    existential = theory.sentences[1]
    check(isinstance(universal, Forall), repr(universal))
    check([v.name for v in universal.variables] == ["i", "C"], repr(universal.variables))
    check(universal.variables[0].domain == "PointerID", repr(universal.variables))
    check(universal.variables[1].domain == "ElementID", repr(universal.variables))
    check(isinstance(existential, Exists), repr(existential))
    check([v.name for v in existential.variables] == ["witness"], repr(existential.variables))


def test_question_mark_variables_disambiguate_without_explicit_forall() -> None:
    """Question-mark variables are always variables and are implicitly universally quantified in rules."""
    sentence = parse_one('likes(?person, "tea") -> happy(?person).')

    check(isinstance(sentence, Forall), repr(sentence))
    check([v.name for v in sentence.variables] == ["person"], repr(sentence.variables))
    check(repr(sentence.sentence) == "Implies(likes(?person, tea), happy(?person))", repr(sentence.sentence))


def test_parse_constraints_and_negation_as_failure() -> None:
    """ASP-style constraints and `not` lower to false-headed implications with NAF."""
    sentence = parse_one(":- pointer_type(i, c), required_slot(c, s), not has_slot_value(i, s).")

    check(isinstance(sentence, Forall), repr(sentence))
    inner = sentence.sentence
    check(isinstance(inner, Implies), repr(inner))
    check(isinstance(inner.consequent, Or), repr(inner.consequent))
    check(any(isinstance(op, NegationAsFailure) for op in inner.antecedent.operands), repr(inner.antecedent))


def test_parse_strict_negation_separately_from_naf() -> None:
    """The `~` connective lowers to strict logical negation, not negation-as-failure."""
    sentence = parse_one("p(x) -> ~q(x).")

    check(isinstance(sentence, Forall), repr(sentence))
    consequent = sentence.sentence.consequent
    check(isinstance(consequent, Not), repr(consequent))


def test_parse_infix_math_and_comparisons() -> None:
    """Arithmetic and comparison syntax lower to builtin operator terms."""
    sentence = parse_one("person_age(p, age) & age + 1 >= 18 -> adult(p).")

    antecedent = sentence.sentence.antecedent
    comparison = antecedent.operands[1]
    check(isinstance(comparison, Term), repr(comparison))
    check(comparison.predicate == "ge", repr(comparison))
    check(isinstance(comparison.values[0], Term), repr(comparison.values[0]))
    check(comparison.values[0].predicate == "add", repr(comparison.values[0]))


def test_parse_hilog_predicate_variable_marker() -> None:
    """The `@slot(...)` marker represents a variable in predicate position."""
    sentence = parse_one("all slot, i, v | @slot(i, v) -> has_slot_value(i, slot).")

    antecedent = sentence.sentence.antecedent
    check(isinstance(antecedent.predicate, Variable), repr(antecedent))
    check(antecedent.predicate.name == "slot", repr(antecedent.predicate))


def test_doc_comments_attach_to_next_sentence() -> None:
    """Triple-slash comments are preserved as sentence annotations."""
    sentence = parse_one(
        """
        /// Required slots must have a value.
        /// Missing values violate the closed-world check.
        required(s) & class_slot(c, s) -> required_slot(c, s).
        """
    )

    check(
        sentence.annotations
        == {"comment": "Required slots must have a value.\nMissing values violate the closed-world check."},
        repr(sentence.annotations),
    )


def test_validate_iter_reports_syntax_errors() -> None:
    """Validation reports parser errors without raising."""
    messages = list(TLogParser().validate_iter("p(x) ->."))

    check(len(messages) == 1, repr(messages))
    check("Expected" in messages[0].message, messages[0].message)


def test_registry_discovers_tlog_parser() -> None:
    """The parser registry discovers TLogParser by class name."""
    parser = get_parser("tlog")

    check(isinstance(parser, TLogParser), repr(parser))


def test_registry_discovers_tlog_compiler() -> None:
    """The compiler registry discovers TLogCompiler by class name."""
    compiler = get_compiler("tlog")

    check(isinstance(compiler, TLogCompiler), repr(compiler))


def test_registry_discovers_tlog_markdown_parser() -> None:
    """The parser registry discovers the Markdown wrapper parser by class name."""
    parser = get_parser("tlogmarkdown")

    check(isinstance(parser, TLogMarkdownParser), repr(parser))


def test_parse_literature_style_linkml_rules_example() -> None:
    """The checked-in LinkML rule example exercises declarations, constraints, comments, and HiLog syntax."""
    theory = TLogParser().parse(Path("tests/input/linkml_rules.tlog"))

    check(theory.type_definitions["PointerID"] == "str", repr(theory.type_definitions))
    check(len(theory.predicate_definitions) == 4, repr(theory.predicate_definitions))
    check(len(theory.sentences) == 4, repr(theory.sentences))
    check(theory.sentences[0].annotations["comment"] == "Inherit slots through the class hierarchy.", "bad comment")
    check(isinstance(theory.sentences[-1].sentence.antecedent.predicate, Variable), repr(theory.sentences[-1]))


def test_parse_literate_markdown_tlog_blocks() -> None:
    """Markdown prose can wrap fenced TLog blocks without affecting the parsed theory."""
    theory = TLogMarkdownParser().parse(Path("tests/input/linkml_rules.md"))

    check(theory.type_definitions["PointerID"] == "str", repr(theory.type_definitions))
    check(theory.predicate_definitions[0].predicate == "pointer_type", repr(theory.predicate_definitions))
    check(len(theory.sentences) == 3, repr(theory.sentences))
    check(isinstance(theory.sentences[1], Forall), repr(theory.sentences[1]))
    check(isinstance(theory.sentences[2], Exists), repr(theory.sentences[2]))


def test_tlog_rules_export_to_existing_prolog_compiler() -> None:
    """Non-HiLog TLog rules use the existing compiler pipeline."""
    theory = TLogParser().parse(
        """
        pred parent(parent: str, child: str).
        pred ancestor(ancestor: str, descendant: str).
        ancestor(x, y) :- parent(x, y).
        ancestor(x, y) :- parent(x, z) & ancestor(z, y).
        """
    )

    compiled = PrologCompiler().compile(theory)
    check("ancestor(X, Y) :- parent(X, Y)." in compiled, compiled)
    check("ancestor(X, Y) :- parent(X, Z), ancestor(Z, Y)." in compiled, compiled)


def test_tlog_compiler_roundtrips_core_tlog_constructs() -> None:
    """The TLog compiler produces syntax that the TLog parser can read back."""
    theory = TLogParser().parse(
        """
        type PersonID: str.
        pred parent(parent: PersonID, child: PersonID).
        pred ancestor(ancestor: PersonID, descendant: PersonID).
        /// Direct parent links are ancestor links.
        ancestor(x, y) :- parent(x, y).
        parent(Alice, Bob).
        """
    )

    compiled = TLogCompiler().compile(theory)
    roundtripped = TLogParser().parse(compiled)
    check("type PersonID: str." in compiled, compiled)
    check("pred parent(parent: PersonID, child: PersonID)." in compiled, compiled)
    check("/// Direct parent links are ancestor links." in compiled, compiled)
    check(roundtripped.type_definitions == theory.type_definitions, repr(roundtripped.type_definitions))
    check(roundtripped.predicate_definitions == theory.predicate_definitions, repr(roundtripped.predicate_definitions))
    check(len(roundtripped.sentences) == len(theory.sentences), repr(roundtripped.sentences))


def test_tlog_type_annotations_export_to_typed_souffle_compiler() -> None:
    """Optional TLog type annotations are available to typed targets."""
    theory = TLogParser().parse(
        """
        type PersonID: str.
        pred parent(parent: PersonID, child: PersonID).
        parent(Alice, Bob).
        """
    )

    compiled = SouffleCompiler().compile(theory)
    check(".type Personid = symbol" in compiled, compiled)
    check(".decl parent(parent: Personid, child: Personid)" in compiled, compiled)
