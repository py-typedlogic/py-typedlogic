"""
Compile a typedlogic :class:`~typedlogic.Theory` to a Maud kinetic model.

The compiler reads the structural facts (see
:mod:`~typedlogic.integrations.frameworks.maud.maud_model`) out of a theory and
renders the kinetic-model portion of a Maud input. The full input folder
(kinetic model + priors + experiments + config) is written by
:func:`~typedlogic.integrations.frameworks.maud.exporter.export_maud_input`,
which uses this compiler for the kinetic-model file.

Only a minimal TOML writer is used so no extra runtime dependency is introduced;
it emits the array-of-inline-tables style that Maud's loader expects.
"""

from dataclasses import dataclass
from typing import Any, ClassVar, Dict, Iterable, List, Optional, Union

from typedlogic import Term, Theory
from typedlogic.compiler import Compiler, ModelSyntax
from typedlogic.datamodel import Extension, Sentence


def render_toml_value(value: Any) -> str:
    """
    Render a scalar (or list) Python value as TOML.

        >>> render_toml_value("c")
        '"c"'
        >>> render_toml_value(True)
        'true'
        >>> render_toml_value(1.0)
        '1.0'
        >>> render_toml_value([1, 2])
        '[1, 2]'
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(render_toml_value(v) for v in value) + "]"
    raise ValueError(f"Cannot render TOML value: {value!r}")


def render_inline_table(mapping: Dict[str, Any]) -> str:
    """
    Render a dict as a TOML inline table.

        >>> render_inline_table({"id": "c", "volume": 1.0})
        '{id = "c", volume = 1.0}'
    """
    parts = [f"{k} = {render_toml_value(v)}" for k, v in mapping.items()]
    return "{" + ", ".join(parts) + "}"


def render_array_of_tables(key: str, rows: List[Dict[str, Any]]) -> List[str]:
    """Render ``key = [ {..}, {..} ]`` as one inline table per line."""
    if not rows:
        return []
    lines = [f"{key} = ["]
    for row in rows:
        lines.append(f"  {render_inline_table(row)},")
    lines.append("]")
    return lines


@dataclass
class MaudCompiler(Compiler):
    """
    A Compiler that generates a Maud ``kinetic_model.toml`` from a Theory.

    Example:
    -------
        >>> from typedlogic import Theory
        >>> from typedlogic.integrations.frameworks.maud.maud_model import (
        ...     Compartment, Metabolite, MetaboliteInCompartment, Reaction,
        ...     ReactionStoichiometry)
        >>> theory = Theory()
        >>> theory.ground_terms = [
        ...     Compartment(id="c", name="cytosol").to_model_object(),
        ...     Metabolite(id="A", name="A").to_model_object(),
        ...     Metabolite(id="B", name="B").to_model_object(),
        ...     MetaboliteInCompartment(metabolite_id="A", compartment_id="c").to_model_object(),
        ...     MetaboliteInCompartment(metabolite_id="B", compartment_id="c").to_model_object(),
        ...     Reaction(id="r1", name="A to B").to_model_object(),
        ...     ReactionStoichiometry(reaction_id="r1", metabolite_id="A",
        ...         compartment_id="c", coefficient=-1.0).to_model_object(),
        ...     ReactionStoichiometry(reaction_id="r1", metabolite_id="B",
        ...         compartment_id="c", coefficient=1.0).to_model_object(),
        ... ]
        >>> print(MaudCompiler().compile(theory))
        compartment = [
          {id = "c", name = "cytosol", volume = 1.0},
        ]
        metabolite = [
          {id = "A", name = "A"},
          {id = "B", name = "B"},
        ]
        metabolite_in_compartment = [
          {metabolite_id = "A", compartment_id = "c", balanced = true},
          {metabolite_id = "B", compartment_id = "c", balanced = true},
        ]
        <BLANKLINE>
        [[reaction]]
        id = "r1"
        name = "A to B"
        mechanism = "reversible_michaelis_menten"
        stoichiometry = {A_c = -1.0, B_c = 1.0}

    :param theory: A Theory holding Maud structural facts.
    :return: kinetic_model.toml as a string.

    """

    default_suffix: ClassVar[str] = "toml"

    def compile(self, theory: Theory, syntax: Optional[Union[str, ModelSyntax]] = None, **kwargs) -> str:
        """Render the theory's structural facts as a ``kinetic_model.toml`` string."""
        by_predicate = _group_terms(theory)
        lines: List[str] = []

        name_terms = by_predicate.get("KineticModel", [])
        if name_terms:
            lines.append(f"name = {render_toml_value(name_terms[0]['name'])}")

        lines += render_array_of_tables(
            "compartment",
            [
                {"id": t["id"], "name": t["name"], "volume": t.get("volume", 1.0)}
                for t in by_predicate.get("Compartment", [])
            ],
        )
        lines += render_array_of_tables(
            "metabolite",
            [{"id": t["id"], "name": t["name"]} for t in by_predicate.get("Metabolite", [])],
        )
        lines += render_array_of_tables(
            "metabolite_in_compartment",
            [
                {
                    "metabolite_id": t["metabolite_id"],
                    "compartment_id": t["compartment_id"],
                    "balanced": bool(t.get("balanced", True)),
                }
                for t in by_predicate.get("MetaboliteInCompartment", [])
            ],
        )
        lines += render_array_of_tables(
            "enzyme",
            [
                {"id": t["id"], "name": t["name"], "subunits": int(t.get("subunits", 1))}
                for t in by_predicate.get("Enzyme", [])
            ],
        )
        lines += render_array_of_tables(
            "enzyme_reaction",
            [
                {"enzyme_id": t["enzyme_id"], "reaction_id": t["reaction_id"]}
                for t in by_predicate.get("EnzymeReaction", [])
            ],
        )

        # Reactions carry an assembled stoichiometry inline table; emit each as a
        # standalone [[reaction]] block for readability.
        stoich_by_reaction = _stoichiometry_by_reaction(by_predicate.get("ReactionStoichiometry", []))
        for t in by_predicate.get("Reaction", []):
            lines.append("")
            lines.append("[[reaction]]")
            lines.append(f"id = {render_toml_value(t['id'])}")
            lines.append(f"name = {render_toml_value(t['name'])}")
            lines.append(f"mechanism = {render_toml_value(t.get('mechanism', 'reversible_michaelis_menten'))}")
            stoich = stoich_by_reaction.get(t["id"], {})
            lines.append(f"stoichiometry = {render_inline_table(stoich)}")

        lines += _render_optional_block(
            "allostery",
            by_predicate.get("Allostery", []),
            ["enzyme_id", "metabolite_id", "compartment_id", "modification_type"],
        )
        lines += _render_optional_block(
            "competitive_inhibition",
            by_predicate.get("CompetitiveInhibition", []),
            ["enzyme_id", "reaction_id", "metabolite_id", "compartment_id"],
        )

        return "\n".join(lines).strip("\n")


def _render_optional_block(name: str, terms: List[Dict[str, Any]], keys: List[str]) -> List[str]:
    lines: List[str] = []
    for t in terms:
        lines.append("")
        lines.append(f"[[{name}]]")
        for k in keys:
            lines.append(f"{k} = {render_toml_value(t[k])}")
    return lines


def _stoichiometry_by_reaction(terms: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    for t in terms:
        mic_key = f"{t['metabolite_id']}_{t['compartment_id']}"
        out.setdefault(t["reaction_id"], {})[mic_key] = t["coefficient"]
    return out


def _field_order() -> Dict[str, List[str]]:
    """
    Map each Maud predicate name to its declared field order.

    Used to name the arguments of *positional* terms, e.g. facts materialised by
    a solver, which come back as ``arg0``, ``arg1``, ... rather than as named
    bindings.
    """
    import dataclasses

    from typedlogic.integrations.frameworks.maud import maud_model

    order: Dict[str, List[str]] = {}
    for obj in vars(maud_model).values():
        if isinstance(obj, type) and dataclasses.is_dataclass(obj):
            order[obj.__name__] = [f.name for f in dataclasses.fields(obj)]
    return order


def _term_to_dict(term: Term, field_order: Dict[str, List[str]]) -> Dict[str, Any]:
    bindings = dict(term.bindings)
    if bindings and all(k.startswith("arg") and k[3:].isdigit() for k in bindings):
        names = field_order.get(term.predicate)
        if names and len(names) >= len(term.values):
            return {names[i]: v for i, v in enumerate(term.values)}
    return bindings


def _group_terms(theory: Theory) -> Dict[str, List[Dict[str, Any]]]:
    """Group ground terms of a theory by predicate, as name->value dicts."""
    field_order = _field_order()
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for term in _iter_ground_terms(theory):
        grouped.setdefault(term.predicate, []).append(_term_to_dict(term, field_order))
    return grouped


def _iter_ground_terms(theory: Theory) -> Iterable[Term]:
    """Yield all ground terms held by a theory (ground_terms and sentences)."""
    seen: List[Term] = list(theory.ground_terms or [])
    for sg in theory.sentence_groups or []:
        for s in sg.sentences or []:
            term = _as_ground_term(s)
            if term is not None:
                seen.append(term)
    return seen


def _as_ground_term(sentence: Sentence) -> Optional[Term]:
    if isinstance(sentence, Extension):
        sentence = sentence.to_model_object()
    if isinstance(sentence, Term) and sentence.is_ground and not sentence.is_constant:
        return sentence
    return None
