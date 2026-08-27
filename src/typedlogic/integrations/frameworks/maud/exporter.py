"""
Export a typedlogic theory to a complete Maud input folder.

A Maud run reads a directory containing four files: the kinetic model, priors,
experiments, and a config that ties them together. This module assembles all
four from the structural and numeric facts in a
:class:`~typedlogic.Theory`, delegating the kinetic-model file to
:class:`~typedlogic.integrations.frameworks.maud.maud_compiler.MaudCompiler`.

Typical use::

    from typedlogic.integrations.frameworks.maud.exporter import (
        export_maud_input, theory_from_facts)

    facts = [Compartment(id="c", name="cytosol"), ...]
    export_maud_input(theory_from_facts(facts), "my_model_dir")

The result is a folder that ``maud sample my_model_dir`` can consume.
"""

import os
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Union

from typedlogic import FactMixin, Theory
from typedlogic.integrations.frameworks.maud.maud_compiler import (
    MaudCompiler,
    _group_terms,
    render_toml_value,
)

KINETIC_MODEL_FILE = "kinetic_model.toml"
PRIORS_FILE = "priors.toml"
EXPERIMENTS_FILE = "experiments.toml"
CONFIG_FILE = "config.toml"


@dataclass
class MaudConfig:
    """Options written into Maud's ``config.toml``."""

    name: str = "typedlogic_export"
    likelihood: bool = True
    cmdstanpy_config: Dict[str, Any] = field(
        default_factory=lambda: {"iter_warmup": 200, "iter_sampling": 200, "chains": 4}
    )
    ode_solver_config: Dict[str, Any] = field(
        default_factory=lambda: {"rel_tol": 1e-9, "abs_tol": 1e-9, "max_num_steps": 1000000000}
    )


def theory_from_facts(facts: Iterable[FactMixin]) -> Theory:
    """
    Build a Theory whose ground terms are the given facts.

        >>> from typedlogic.integrations.frameworks.maud.maud_model import Metabolite
        >>> theory = theory_from_facts([Metabolite(id="A", name="A")])
        >>> theory.ground_terms[0].predicate
        'Metabolite'
    """
    theory = Theory()
    theory.ground_terms = [f.to_model_object() for f in facts]
    return theory


def export_maud_input(
    theory: Union[Theory, Iterable[FactMixin]],
    directory: Union[str, os.PathLike],
    config: Union[MaudConfig, None] = None,
) -> Dict[str, str]:
    """
    Write a full Maud input folder from a theory (or iterable of facts).

    :param theory: a Theory of Maud facts, or an iterable of FactMixin facts.
    :param directory: destination folder; created if it does not exist.
    :param config: optional :class:`MaudConfig`.
    :return: mapping of filename -> written content.
    """
    if not isinstance(theory, Theory):
        theory = theory_from_facts(theory)
    if config is None:
        config = MaudConfig()

    by_predicate = _group_terms(theory)
    contents = {
        KINETIC_MODEL_FILE: MaudCompiler().compile(theory),
        PRIORS_FILE: _render_priors(by_predicate),
        EXPERIMENTS_FILE: _render_experiments(by_predicate),
        CONFIG_FILE: _render_config(config),
    }

    os.makedirs(directory, exist_ok=True)
    for filename, text in contents.items():
        with open(os.path.join(directory, filename), "w", encoding="utf-8") as f:
            f.write(text.rstrip("\n") + "\n")
    return contents


def _render_priors(by_predicate: Dict[str, List[Dict[str, Any]]]) -> str:
    lines: List[str] = []
    for t in by_predicate.get("KcatPrior", []):
        lines += ["", "[[kcat]]"]
        for k in ("enzyme", "reaction", "location", "scale"):
            lines.append(f"{k} = {render_toml_value(t[k])}")
    for t in by_predicate.get("KmPrior", []):
        lines += ["", "[[km]]"]
        for k in ("metabolite", "compartment", "enzyme", "reaction", "exploc", "scale"):
            lines.append(f"{k} = {render_toml_value(t[k])}")

    # Formation-energy priors are aggregated into one multivariate dgf prior with
    # a diagonal covariance built from the individual scales (variance = scale^2).
    dgf = by_predicate.get("FormationEnergyPrior", [])
    if dgf:
        ids = [t["metabolite"] for t in dgf]
        means = [t["location"] for t in dgf]
        cov = [[float(t["scale"]) ** 2 if i == j else 0.0 for j in range(len(dgf))] for i, t in enumerate(dgf)]
        lines += ["", "[dgf]"]
        lines.append(f"ids = {render_toml_value(ids)}")
        lines.append(f"mean_vector = {render_toml_value(means)}")
        lines.append(f"covariance_matrix = {render_toml_value(cov)}")

    return "\n".join(lines).strip("\n")


def _render_experiments(by_predicate: Dict[str, List[Dict[str, Any]]]) -> str:
    measurements_by_experiment: Dict[str, List[Dict[str, Any]]] = {}
    for m in by_predicate.get("Measurement", []):
        measurements_by_experiment.setdefault(m["experiment_id"], []).append(m)

    lines: List[str] = []
    for exp in by_predicate.get("Experiment", []):
        lines += ["", "[[experiment]]"]
        lines.append(f"id = {render_toml_value(exp['id'])}")
        lines.append(f"is_train = {render_toml_value(bool(exp.get('is_train', True)))}")
        lines.append(f"is_test = {render_toml_value(bool(exp.get('is_test', False)))}")
        lines.append(f"temperature = {render_toml_value(exp.get('temperature', 298.15))}")
        for m in measurements_by_experiment.get(exp["id"], []):
            lines += ["", "[[experiment.measurements]]"]
            lines.append(f"target_type = {render_toml_value(m['target_type'])}")
            # Maud names the target key by type: `metabolite` for mic, `reaction` for flux.
            if m["target_type"] == "flux":
                lines.append(f"reaction = {render_toml_value(m['target_id'])}")
            else:
                lines.append(f"metabolite = {render_toml_value(m['target_id'])}")
                if m.get("compartment") is not None:
                    lines.append(f"compartment = {render_toml_value(m['compartment'])}")
            lines.append(f"value = {render_toml_value(m['value'])}")
            lines.append(f"error_scale = {render_toml_value(m['error_scale'])}")

    return "\n".join(lines).strip("\n")


def _render_config(config: MaudConfig) -> str:
    lines = [
        f"name = {render_toml_value(config.name)}",
        f"kinetic_model_file = {render_toml_value(KINETIC_MODEL_FILE)}",
        f"priors_file = {render_toml_value(PRIORS_FILE)}",
        f"experiments_file = {render_toml_value(EXPERIMENTS_FILE)}",
        f"likelihood = {render_toml_value(config.likelihood)}",
    ]
    lines += ["", "[cmdstanpy_config]"]
    for k, v in config.cmdstanpy_config.items():
        lines.append(f"{k} = {render_toml_value(v)}")
    lines += ["", "[ode_solver_config]"]
    for k, v in config.ode_solver_config.items():
        lines.append(f"{k} = {render_toml_value(v)}")
    return "\n".join(lines)
