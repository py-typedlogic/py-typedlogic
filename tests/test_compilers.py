import pytest

import tests.theorems.animals as animals
import tests.theorems.defined_types_example as defined_types_example
import tests.theorems.ehr_phenotyping as ehr_phenotyping
import tests.theorems.enums_example as enums_example
import tests.theorems.gluconeogenesis as gluconeogenesis
import tests.theorems.import_test.ext as import_test_ext
import tests.theorems.mortals as mortals
import tests.theorems.numbers as numbers
import tests.theorems.optional_example as optional_example
import tests.theorems.paths as paths
import tests.theorems.paths_with_distance as pwd
import tests.theorems.signaling_pathways as signaling_pathways
import tests.theorems.simple_contradiction as simple_contradiction
import tests.theorems.types_example as types_example
import typedlogic.integrations.frameworks.linkml.meta as linkml_meta
import typedlogic.integrations.frameworks.linkml.meta_axioms as linkml_meta_axioms
from tests import SNAPSHOTS_DIR
from tests.theorems import barbers, unary_predicates
from typedlogic import And, Forall, Implies, NegationAsFailure, Not, PredicateDefinition, Term, Theory, Variable
from typedlogic.compilers.clif_compiler import ClifCompiler
from typedlogic.compilers.fol_compiler import FOLCompiler
from typedlogic.compilers.prolog_compiler import PrologCompiler
from typedlogic.compilers.prover9_compiler import Prover9Compiler
from typedlogic.compilers.sexpr_compiler import SExprCompiler
from typedlogic.compilers.tptp_compiler import TPTPCompiler
from typedlogic.compilers.yaml_compiler import YAMLCompiler
from typedlogic.datamodel import NotInProfileError
from typedlogic.integrations.solvers.problog.problog_compiler import ProbLogCompiler
from typedlogic.integrations.solvers.souffle.souffle_compiler import SouffleCompiler
from typedlogic.integrations.solvers.z3.z3_compiler import Z3Compiler, Z3FunctionalCompiler, Z3SExprCompiler
from typedlogic.parsers.pyparser.introspection import translate_module_to_theory
from typedlogic.registry import all_compiler_classes, all_parser_classes


@pytest.mark.parametrize(
    "compiler_class",
    [
        FOLCompiler,
        Z3SExprCompiler,
        Z3FunctionalCompiler,
        PrologCompiler,
        SouffleCompiler,
        TPTPCompiler,
        Prover9Compiler,
        YAMLCompiler,
        SExprCompiler,
        ProbLogCompiler,
        ClifCompiler,
    ],
)
@pytest.mark.parametrize(
    "theory_module",
    [
        animals,
        barbers,
        defined_types_example,
        ehr_phenotyping,
        pwd,
        enums_example,
        # signaling_pathways,
        # gluconeogenesis,  ## lists not supported
        mortals,
        import_test_ext,
        numbers,
        paths,
        optional_example,
        simple_contradiction,
        unary_predicates,
        types_example,
        linkml_meta,
        linkml_meta_axioms,
    ],
)
def test_compiler(compiler_class, theory_module):
    if issubclass(compiler_class, Z3Compiler) and theory_module == defined_types_example:
        pytest.skip("Z3Solver does not support defined types")
    if issubclass(compiler_class, Z3Compiler) and theory_module == optional_example:
        pytest.skip("Z3Solver does not support defined Optional")
    if issubclass(compiler_class, Z3Compiler) and theory_module == ehr_phenotyping:
        pytest.skip("Z3Solver does not support date")
    theory = translate_module_to_theory(theory_module)
    compiler = compiler_class()
    compiled = compiler.compile(theory)
    print(compiled)
    fn = f"{theory_module.__name__}-{compiler_class.__name__}.{compiler.suffix}"
    with open(SNAPSHOTS_DIR / fn, "w", encoding="utf-8") as f:
        f.write(compiled)
    # roundtrip for cases where the a parser exists
    all_parsers = all_parser_classes()
    all_compilers = all_compiler_classes()
    [compiler_name] = [k for k, v in all_compilers.items() if v == compiler_class]
    if compiler_name in all_parsers:
        if compiler_name == "prolog":
            # TODO
            return
        parser = all_parsers[compiler_name]()
        parser.parse(compiled)
        with open(SNAPSHOTS_DIR / fn) as f:
            roundtripped = parser.parse(f)
            compiled2 = compiler.compile(roundtripped)
            if compiler_name == "prolog":
                pass
            else:
                assert compiled2 == compiled


def _person_robot_theory():
    """Build a small theory containing a constraint with no Horn-rule translation."""
    x = Variable("x", "str")
    theory = Theory(
        name="people",
        predicate_definitions=[
            PredicateDefinition("Person", {"name": "str"}),
            PredicateDefinition("Robot", {"name": "str"}),
        ],
    )
    theory.add(Forall([x], Implies(Term("Person", x), Not(Term("Robot", x)))))
    return theory


def test_prolog_compiler_emits_ground_terms():
    """Ground terms attached directly to the theory must appear in the Prolog output."""
    theory = _person_robot_theory()
    theory.ground_terms.append(Term("Person", "Fred"))
    compiled = PrologCompiler().compile(theory)
    assert "person('Fred')." in compiled


def test_prolog_compiler_marks_dropped_constraints_untranslatable():
    """A constraint with no Horn-rule translation is marked rather than silently dropped."""
    theory = _person_robot_theory()
    compiled = PrologCompiler().compile(theory)
    assert "%% UNTRANSLATABLE" in compiled
    assert "¬Robot" in compiled


def test_prolog_compiler_strict_raises_on_dropped_constraints():
    """In strict mode, untranslatable sentences raise instead of being commented out."""
    theory = _person_robot_theory()
    with pytest.raises(NotInProfileError):
        PrologCompiler(strict=True).compile(theory)


def _naf_mixed_theory() -> Theory:
    """Build a theory mixing one NAF rule with a classical implication."""
    from typedlogic.datamodel import NegationAsFailure

    x = Variable("x", "str")
    theory = Theory(
        predicate_definitions=[
            PredicateDefinition("p", {"x": "str"}),
            PredicateDefinition("q", {"x": "str"}),
            PredicateDefinition("r", {"x": "str"}),
        ],
    )
    theory.add(Forall([x], Implies(Term("p", x), Term("q", x))))
    theory.add(Forall([x], Implies(And(Term("p", x), NegationAsFailure(Term("q", x))), Term("r", x))))
    return theory


def test_p9_compiler_skips_naf_sentences(caplog):
    """One NAF rule must not crash Prover9 compilation of a mixed theory.

    Named p9 rather than prover9: this exercises only the compiler, and conftest
    skips any test with "prover9" in its id when the executable is missing.
    """
    import logging

    with caplog.at_level(logging.WARNING):
        compiled = Prover9Compiler().compile(_naf_mixed_theory())
    assert any("negation-as-failure" in rec.message for rec in caplog.records)
    assert "p(x) -> q(x)" in compiled
    assert "r(x)" not in compiled


def test_tptp_compiler_skips_naf_sentences(caplog):
    """One NAF rule must not crash TPTP compilation of a mixed theory."""
    import logging

    with caplog.at_level(logging.WARNING):
        compiled = TPTPCompiler().compile(_naf_mixed_theory())
    assert any("negation-as-failure" in rec.message for rec in caplog.records)
    assert "fof(axiom1, axiom, ! [X] : (p(X) => q(X)))." in compiled
    assert "axiom2" not in compiled
def _typed_theory(**type_definitions):
    """Build a theory whose predicate brands both of its arguments with defined types."""
    return Theory(
        name="typed",
        type_definitions=dict(type_definitions),
        predicate_definitions=[PredicateDefinition("Employs", {"org": "OrgID", "person": "PersonID"})],
    )


def test_souffle_compiler_brands_defined_types_as_subtypes():
    """Defined types compile to Souffle subtypes, so Souffle enforces the branding.

    With ``=`` the name is a mere alias and OrgID/PersonID stay mutually assignable.
    """
    theory = _typed_theory(OrgID="str", PersonID="str")
    compiled = SouffleCompiler().compile(theory)
    assert ".type OrgID <: symbol" in compiled
    assert ".type PersonID <: symbol" in compiled
    assert ".decl Employs(org: OrgID, person: PersonID)" in compiled


def test_souffle_compiler_subtype_branding_can_be_disabled():
    """Arithmetic over a branded numeric type needs alias semantics, so it stays available."""
    theory = _typed_theory(OrgID="str", PersonID="str")
    compiled = SouffleCompiler(strict_subtypes=False).compile(theory)
    assert ".type OrgID = symbol" in compiled
    assert "<:" not in compiled


def test_souffle_compiler_preserves_type_name_case():
    """Type names are emitted verbatim; capitalizing them collided distinct names."""
    theory = Theory(
        name="casing",
        type_definitions={"PersonID": "str", "PersonId": "int"},
        predicate_definitions=[PredicateDefinition("P", {"a": "PersonID", "b": "PersonId"})],
    )
    compiled = SouffleCompiler().compile(theory)
    assert ".type PersonID <: symbol" in compiled
    assert ".type PersonId <: number" in compiled
    assert "Personid" not in compiled


def test_souffle_compiler_omits_unreferenced_type_definitions():
    """A type no predicate mentions cannot brand anything, so it is not declared.

    Plain Python aliases (``NameType = str``) are erased before introspection, and used
    to surface here as declarations implying an enforcement that did not exist.
    """
    theory = _typed_theory(OrgID="str", PersonID="str", Unused="str")
    compiled = SouffleCompiler().compile(theory)
    assert "Unused" not in compiled


def test_souffle_compiler_emits_transitively_referenced_types():
    """A type reached only through another type definition is still declared."""
    theory = _typed_theory(OrgID="Identifier", PersonID="Identifier", Identifier="str")
    compiled = SouffleCompiler().compile(theory)
    assert ".type Identifier <: symbol" in compiled
    assert ".type OrgID <: Identifier" in compiled


def test_souffle_compiler_renames_types_clashing_with_primitives():
    """A defined type named after a Souffle primitive must not redefine that primitive."""
    theory = Theory(
        name="clash",
        type_definitions={"symbol": "str"},
        predicate_definitions=[PredicateDefinition("P", {"a": "symbol"})],
    )
    compiled = SouffleCompiler().compile(theory)
    assert ".type symbol_t <: symbol" in compiled
    assert ".decl P(a: symbol_t)" in compiled


def test_souffle_compiler_unions_stay_aliases_and_resolve_members():
    """A union is a sum of its members, so it keeps ``=`` and names defined members."""
    theory = Theory(
        name="unions",
        type_definitions={"Identifier": "str", "Key": ["Identifier", "int"]},
        predicate_definitions=[PredicateDefinition("P", {"k": "Key"})],
    )
    compiled = SouffleCompiler().compile(theory)
    assert ".type Key = Identifier | number" in compiled


def test_souffle_compiler_newtype_branding_survives_python_introspection():
    """End to end: a NewType declared in Python reaches the Souffle declaration.

    Pydantic's JSON schema resolves NewTypes away, which previously erased the brand
    before it could reach any compiler.
    """
    theory = translate_module_to_theory(defined_types_example)
    assert theory.predicate_definition_map["PersonWithAddress"].arguments["zip_code"] == "ZipCode"
    compiled = SouffleCompiler().compile(theory)
    assert ".type ZipCode <: symbol" in compiled
    assert ".decl PersonWithAddress(name: symbol, zip_code: ZipCode)" in compiled


@pytest.mark.parametrize(
    "compiler_class,expected",
    [
        (PrologCompiler, r"\+ (abnormal(X))"),
        (SouffleCompiler, "! (Abnormal(x))"),
        (ProbLogCompiler, r"\+ abnormal(X)"),
    ],
    # These ids deliberately avoid the substring "souffle": tests/conftest.py skips any test
    # whose nodeid contains it, on the assumption that the souffle binary is needed. These
    # cases only exercise the compiler, so they should run everywhere.
    ids=["prolog", "datalog", "problog"],
)
def test_negation_as_failure_rendering(compiler_class, expected):
    """Each Datalog/Prolog dialect must render negation-as-failure in its own syntax.

    Regression: Souffle spells stratified negation ``!``, but only ``negation_symbol`` was
    configured, so NAF fell back to the Prolog default and emitted a program Souffle cannot parse.
    """
    x = Variable("x")
    theory = Theory()
    for pred in ("Bird", "Abnormal", "Flies"):
        theory.predicate_definitions.append(PredicateDefinition(pred, {"x": "str"}))
    theory.add(Implies(And(Term("Bird", x), NegationAsFailure(Term("Abnormal", x))), Term("Flies", x)))

    program = compiler_class().compile(theory)
    assert expected in program
    assert "not_provable" not in program


def test_negation_as_failure_not_in_classical_profile():
    """CLIF is classical FOL and must reject negation-as-failure rather than silently accept it."""
    x = Variable("x")
    theory = Theory()
    for pred in ("Bird", "Abnormal", "Flies"):
        theory.predicate_definitions.append(PredicateDefinition(pred, {"x": "str"}))
    theory.add(Implies(And(Term("Bird", x), NegationAsFailure(Term("Abnormal", x))), Term("Flies", x)))

    with pytest.raises(NotInProfileError):
        ClifCompiler().compile(theory)
