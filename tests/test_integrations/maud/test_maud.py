"""
Tests for the Maud exporter integration.

These validate that a typedlogic theory of structural + numeric facts is exported
as a well-formed Maud input folder. Output is parsed back with ``tomllib`` and
checked against Maud's expected structure.
"""

import sys

import pytest

import tests.theorems.maud_linear as maud_linear
from typedlogic import Theory
from typedlogic.integrations.frameworks.maud.exporter import (
    CONFIG_FILE,
    EXPERIMENTS_FILE,
    KINETIC_MODEL_FILE,
    PRIORS_FILE,
    MaudConfig,
    export_maud_input,
    theory_from_facts,
)
from typedlogic.integrations.frameworks.maud.maud_compiler import (
    MaudCompiler,
    render_inline_table,
    render_toml_value,
)
from typedlogic.integrations.frameworks.maud.maud_model import (
    Compartment,
    Metabolite,
    MetaboliteInCompartment,
    Reaction,
    ReactionStoichiometry,
)
from typedlogic.registry import get_compiler

tomllib = pytest.importorskip("tomllib") if sys.version_info >= (3, 11) else pytest.importorskip("tomli")


def _parse(text: str) -> dict:
    return tomllib.loads(text)


# --- rendering helpers ---


@pytest.mark.parametrize(
    "value,expected",
    [
        ("c", '"c"'),
        (True, "true"),
        (False, "false"),
        (1, "1"),
        (1.5, "1.5"),
        ([1, 2], "[1, 2]"),
        (["a", "b"], '["a", "b"]'),
    ],
)
def test_render_toml_value(value, expected):
    assert render_toml_value(value) == expected


def test_render_inline_table():
    assert render_inline_table({"id": "c", "volume": 1.0}) == '{id = "c", volume = 1.0}'


def test_string_escaping_roundtrips():
    text = render_toml_value('a "quoted" name')
    assert _parse(f"x = {text}") == {"x": 'a "quoted" name'}


# --- compiler / registry ---


def test_compiler_registered():
    compiler = get_compiler("maud")
    assert isinstance(compiler, MaudCompiler)


def test_kinetic_model_minimal():
    theory = theory_from_facts(
        [
            Compartment(id="c", name="cytosol"),
            Metabolite(id="A", name="A"),
            Metabolite(id="B", name="B"),
            MetaboliteInCompartment(metabolite_id="A", compartment_id="c"),
            MetaboliteInCompartment(metabolite_id="B", compartment_id="c"),
            Reaction(id="r1", name="A to B"),
            ReactionStoichiometry(reaction_id="r1", metabolite_id="A", compartment_id="c", coefficient=-1.0),
            ReactionStoichiometry(reaction_id="r1", metabolite_id="B", compartment_id="c", coefficient=1.0),
        ]
    )
    parsed = _parse(MaudCompiler().compile(theory))
    assert parsed["compartment"] == [{"id": "c", "name": "cytosol", "volume": 1.0}]
    assert {m["id"] for m in parsed["metabolite"]} == {"A", "B"}
    assert len(parsed["reaction"]) == 1
    assert parsed["reaction"][0]["stoichiometry"] == {"A_c": -1.0, "B_c": 1.0}


# --- full-folder export from the example model ---


@pytest.fixture
def exported(tmp_path):
    contents = export_maud_input(theory_from_facts(maud_linear.all_facts()), tmp_path)
    return tmp_path, contents


def test_export_writes_all_files(exported):
    tmp_path, _ = exported
    for name in (KINETIC_MODEL_FILE, PRIORS_FILE, EXPERIMENTS_FILE, CONFIG_FILE):
        assert (tmp_path / name).exists()


def test_kinetic_model_structure(exported):
    tmp_path, _ = exported
    km = _parse((tmp_path / KINETIC_MODEL_FILE).read_text())
    assert km["name"] == "linear"
    assert {c["id"] for c in km["compartment"]} == {"e", "c"}
    assert {m["id"] for m in km["metabolite"]} == {"M1", "M2"}
    # Boundary species unbalanced, internal balanced.
    mics = {(m["metabolite_id"], m["compartment_id"]): m["balanced"] for m in km["metabolite_in_compartment"]}
    assert mics[("M1", "e")] is False
    assert mics[("M1", "c")] is True
    # Three reactions, each with an assembled stoichiometry table.
    reactions = {r["id"]: r for r in km["reaction"]}
    assert set(reactions) == {"r1", "r2", "r3"}
    assert reactions["r2"]["stoichiometry"] == {"M1_c": -1.0, "M2_c": 1.0}
    # Allostery block round-trips.
    assert km["allostery"][0]["enzyme_id"] == "r2"
    assert km["allostery"][0]["modification_type"] == "activation"


def test_priors_structure(exported):
    tmp_path, _ = exported
    priors = _parse((tmp_path / PRIORS_FILE).read_text())
    assert {k["enzyme"] for k in priors["kcat"]} == {"r1", "r2", "r3"}
    # Formation energies aggregate into one multivariate dgf prior.
    dgf = priors["dgf"]
    assert dgf["ids"] == ["M1", "M2"]
    assert dgf["mean_vector"] == [-1.0, 2.0]
    # Diagonal covariance from scale^2 (scale 0.5 -> 0.25).
    assert dgf["covariance_matrix"] == [[0.25, 0.0], [0.0, 0.25]]


def test_experiments_structure(exported):
    tmp_path, _ = exported
    experiments = _parse((tmp_path / EXPERIMENTS_FILE).read_text())
    exp = experiments["experiment"][0]
    assert exp["id"] == "condition_1"
    assert exp["is_train"] is True
    measurements = exp["measurements"]
    assert {m["metabolite"] for m in measurements} == {"M1", "M2"}
    assert all(m["target_type"] == "mic" for m in measurements)
    assert all(m["compartment"] == "c" for m in measurements)


def test_config_structure(exported):
    tmp_path, _ = exported
    config = _parse((tmp_path / CONFIG_FILE).read_text())
    assert config["kinetic_model_file"] == KINETIC_MODEL_FILE
    assert config["priors_file"] == PRIORS_FILE
    assert config["experiments_file"] == EXPERIMENTS_FILE
    assert config["likelihood"] is True
    assert config["cmdstanpy_config"]["chains"] == 4


def test_custom_config(tmp_path):
    cfg = MaudConfig(name="my_run", likelihood=False)
    export_maud_input(theory_from_facts(maud_linear.structural_facts()), tmp_path, config=cfg)
    config = _parse((tmp_path / CONFIG_FILE).read_text())
    assert config["name"] == "my_run"
    assert config["likelihood"] is False


def test_export_accepts_iterable_of_facts(tmp_path):
    # export_maud_input should accept a bare iterable of facts, not only a Theory.
    export_maud_input(maud_linear.structural_facts(), tmp_path)
    km = _parse((tmp_path / KINETIC_MODEL_FILE).read_text())
    assert km["name"] == "linear"


# --- derivation via a solver (structure generated, then exported) ---


def test_enzyme_reaction_derived_and_exported(tmp_path):
    """
    The example asserts Catalyzes facts, not EnzymeReaction facts. A datalog
    solver materialises EnzymeReaction via the axiom; the exporter then emits the
    Maud enzyme_reaction associations. This is the core "typedlogic derives the
    structure Maud needs" demonstration.

    The pure-Python ``wellfounded`` solver is used so no external binary is
    required; ``souffle`` is tried as a fallback.
    """
    from typedlogic.parsers.pyparser.python_parser import PythonParser
    from typedlogic.registry import get_solver

    theory = PythonParser().transform(maud_linear)
    model = None
    last_error = None
    for handle in ("wellfounded", "souffle"):
        try:
            solver = get_solver(handle)
            solver.add(theory)
            for fact in maud_linear.all_facts():
                solver.add_fact(fact)
            assert solver.check().satisfiable is not False
            model = solver.model()
            break
        except Exception as e:  # pragma: no cover - solver unavailable
            last_error = e
    if model is None:  # pragma: no cover - no usable solver
        pytest.skip(f"no datalog solver available: {last_error}")

    derived = Theory()
    derived.ground_terms = list(model.ground_terms)
    export_maud_input(derived, tmp_path)
    km = _parse((tmp_path / KINETIC_MODEL_FILE).read_text())
    enzyme_reactions = {(er["enzyme_id"], er["reaction_id"]) for er in km.get("enzyme_reaction", [])}
    assert ("r1", "r1") in enzyme_reactions
    assert ("r2", "r2") in enzyme_reactions
    assert ("r3", "r3") in enzyme_reactions
