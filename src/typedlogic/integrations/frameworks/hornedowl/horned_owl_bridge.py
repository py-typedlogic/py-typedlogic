"""
Bridge between typedlogic OWL model and py-horned-owl.


"""
import logging
from dataclasses import dataclass, field
from typing import Any, List, Dict

from typedlogic import Theory, PredicateDefinition, And
from typedlogic.integrations.frameworks.owldl import Thing, TopDataProperty, TopObjectProperty
import typedlogic.integrations.frameworks.owldl.owltop as owltop

import pyhornedowl  # type: ignore
from pyhornedowl.model import DataPropertyAssertion  # type: ignore
from pyhornedowl.model import ObjectPropertyAssertion, AnnotationAssertion, SimpleLiteral, DatatypeLiteral, LanguageLiteral, IRI, NamedIndividual, Class, ObjectProperty, DataProperty  # type: ignore
from rdflib import RDFS
from typedlogic.integrations.frameworks.owldl.owltop import OntologyElement

logger = logging.getLogger(__name__)

@dataclass
class ConversionContext:
    """
    Additional context and configuration for the conversion to/from py-horned-owl.
    """
    label_map: Dict[str, str] = field(default_factory=dict)
    decl_map: Dict[str, str] = field(default_factory=dict)
    ontology: pyhornedowl.PyIndexedOntology = field(default_factory=pyhornedowl.PyIndexedOntology)

def load_ontology(source: str) -> List[owltop.Axiom]:
    """
    Load an OWL ontology using py-horned-owl, translating to tl-owl axioms

    :param ontology:
    :return:
    """
    onto = pyhornedowl.open_ontology(str(source))
    sentences = py_indexed_ontology_to_pyowl(onto)
    return sentences


def _get_label_map(ontology: pyhornedowl.PyIndexedOntology) -> Dict[str, str]:
    """
    Get the label map from the ontology.

    :param ontology:
    :return:
    """
    label_map = {}
    for oc in ontology.get_axioms():
        a = oc.component
        if isinstance(a, AnnotationAssertion):
            ann = a.ann
            ap = ann.ap
            if str(ap.first) == str(RDFS.label):
                if isinstance(ann.av, (SimpleLiteral, LanguageLiteral, DatatypeLiteral)):
                    lbl = ann.av.literal
                    lbl = lbl.replace(" ", "_").replace("-", "_")
                    # check if starts with number:
                    if lbl[0].isdigit():
                        lbl = "x" + lbl
                    label_map[str(a.subject)] = lbl
    return label_map

def py_indexed_ontology_to_pyowl(ontology: pyhornedowl.PyIndexedOntology) -> List[owltop.Axiom]:
    """
    Convert the PHO ontology to PyOwl.

    :param ontology:
    :return:
    """
    axioms: List[owltop.Axiom] = []
    label_map = {}
    for oc in ontology.get_axioms():
        a = oc.component
        if isinstance(a, AnnotationAssertion):
            ann = a.ann
            ap = ann.ap
            if str(ap.first) == str(RDFS.label):
                if isinstance(ann.av, (SimpleLiteral, LanguageLiteral, DatatypeLiteral)):
                    lbl = ann.av.literal
                    lbl = lbl.replace(" ", "_").replace("-", "_")
                    # check if starts with number:
                    if lbl[0].isdigit():
                        lbl = "x" + lbl
                    label_map[str(a.subject)] = lbl
    for oc in ontology.get_axioms():
        a = oc.component
        # anns = oc.ann
        axiom = tr(a, label_map, parent=a)
        if isinstance(axiom, owltop.Axiom):
            axioms.append(axiom)
    return axioms

def parse_owl_ontology_to_theory(source: str) -> Theory:
    """
    Parse an OWL ontology from a file to a theory.

    This is just the composition of py-horned-owl's `open_ontology` and `py_indexed_ontology_to_theory`.

    Example:

        >>> theory = parse_owl_ontology_to_theory("tests/test_frameworks/hornedowl/input/ro.ofn")
        >>> for pd in theory.predicate_definitions:
        ...     print(pd.predicate, pd.parents)
        <BLANKLINE>
        ...
        continuant ['Thing']
        ...
        <BLANKLINE>

    :param source:
    :return:
    """
    onto = pyhornedowl.open_ontology(source)
    return py_indexed_ontology_to_theory(onto)


def py_indexed_ontology_to_theory(ontology: pyhornedowl.PyIndexedOntology) -> Theory:
    """
    Convert the PHO ontology to a theory.

    Example:

        >>> onto = pyhornedowl.open_ontology("tests/test_frameworks/hornedowl/input/ro.ofn")
        >>> theory = py_indexed_ontology_to_theory(onto)
        >>> for pd in theory.predicate_definitions:
        ...     print(pd.predicate, pd.parents)
        <BLANKLINE>
        ...
        continuant ['Thing']
        ...
        <BLANKLINE>
        >>> for s in theory.sentences:
        ...     print(s)
        <BLANKLINE>
        ...
        ∀I: None, J: None : (surrounded_by(?I, ?J) <-> surrounds(?J, ?I))
        ...
        <BLANKLINE>

    :param ontology:
    :return:
    """
    axioms = py_indexed_ontology_to_pyowl(ontology)
    theory = Theory()
    for a in axioms:
        s = a.as_fol()
        if not s:
            s = And()
        s.add_annotation("owl_axiom", a)
        theory.add(s)
    label_map = _get_label_map(ontology)
    for c in ontology.get_classes():
        entity_lbl = label_map.get(c, c)
        pd = PredicateDefinition(entity_lbl, arguments={"iri": "str"}, parents=["Thing"])
        theory.predicate_definitions.append(pd)
    for op in ontology.get_object_properties():
        entity_lbl = label_map.get(op, op)
        pd = PredicateDefinition(entity_lbl, arguments={"subject": "str", "object": "str"}, parents=["TopObjectProperty"])
        theory.predicate_definitions.append(pd)
    # TODO: PHO does not return data properties?
    return theory

def tr(x: Any, label_map: Dict[str, str], parent=None) -> Any:
    """
    Translate the axiom.

    :param x:
    :return:
    """
    if isinstance(x, list):
        return [tr(i, label_map) for i in x]
    if isinstance(x, IRI):
        return str(x)
    if isinstance(x, NamedIndividual):
        return str(x.first)
    if isinstance(x, (Class, ObjectProperty, DataProperty)):
        if isinstance(x, Class):
            superclass = Thing
        elif isinstance(x, ObjectProperty):
            superclass = TopObjectProperty
        elif isinstance(x, DataProperty):
            superclass = TopDataProperty

        entity_iri = str(x.first)
        def class_body(namespace):
            namespace["iri"] = entity_iri
        entity_lbl = label_map.get(entity_iri, entity_iri)
        if entity_lbl.startswith("http"):
            entity_lbl = entity_lbl.split("/")[-1]
        # replace any non alpha-numeric characters with _
        entity_lbl = "".join([c if c.isalnum() else "_" for c in entity_lbl])
        return OntologyElement(entity_lbl, type(x).__name__, entity_iri)
        # entity_lbl = entity_lbl.replace("#", "_").replace(":", "_")
        #py_cls = types.new_class(entity_lbl, (superclass,), {}, class_body)
        #py_cls.__module__ = "__temp__"
        #return py_cls
    typ = type(x)
    typ_name = typ.__name__
    if typ_name in owltop.__dict__:
        tl_cls = owltop.__dict__[typ_name]
        kwargs = {}
        for k in x.__dir__():
            if not k.startswith("__"):
                v = getattr(x, k)
                kwargs[k] = tr(v, label_map)
        args = kwargs.values()
        if tl_cls == owltop.SubObjectPropertyOf and isinstance(kwargs["sub"], list):
            # https://github.com/ontology-tools/py-horned-owl/issues/32
            obj = tl_cls(owltop.PropertyExpressionChain(*kwargs["sub"]), kwargs["sup"])
        elif tl_cls == owltop.ObjectHasSelf:
            obj = tl_cls(*args)
        else:
            if "first" in kwargs and isinstance(kwargs["first"], list):
                obj = tl_cls(*kwargs["first"])
            else:
                obj = tl_cls(**kwargs)
        return obj
    return x

def rev_tr(x: Any, context: ConversionContext) -> Any:
    """
    Reverse translate the axiom from PyOwl to py-horned-owl.

    Examples:

        >>> from typedlogic.integrations.frameworks.owldl.owltop import OntologyElement
        >>> o = pyhornedowl.PyIndexedOntology()
        >>> o.add_prefix_mapping("", "https://example.com/")
        >>> A = OntologyElement("A", "Class")
        >>> B = OntologyElement("B", "Class")
        >>> context = ConversionContext(ontology=o)
        >>> pho_axiom = rev_tr(owltop.SubClassOf(A, B), context)
        >>> print(type(pho_axiom).__name__, pho_axiom.sub, pho_axiom.sup)
        SubClassOf https://example.com/A https://example.com/B

        >>> P = OntologyElement("P", "ObjectProperty")
        >>> Q = OntologyElement("Q", "ObjectProperty")
        >>> pho_axiom = rev_tr(owltop.SubObjectPropertyOf(P, Q), context)
        >>> print(type(pho_axiom).__name__, pho_axiom.sub, pho_axiom.sup)
        SubObjectPropertyOf https://example.com/P https://example.com/Q

        >>> svf = owltop.ObjectSomeValuesFrom(P, B)
        >>> pho_axiom = rev_tr(owltop.SubClassOf(A, svf), context)
        >>> print(type(pho_axiom).__name__, pho_axiom.sub,  pho_axiom.sup.ope, pho_axiom.sup.bce)
        SubClassOf https://example.com/A https://example.com/P https://example.com/B

    :param x:
    :param label_map:
    :return:
    """
    if isinstance(x, str):
        decl_map = context.decl_map
        o = context.ontology
        decl_type = decl_map.get(x)
        x = OntologyElement(x, decl_type, None)
    if isinstance(x, OntologyElement):
        decl_type = x.owl_type
        iri = x.iri or x.__name__
        o = context.ontology
        if decl_type == "Class":
            return o.clazz(iri)
        if decl_type == "ObjectProperty":
            return o.object_property(iri)
        if decl_type == "DataProperty":
            return o.data_property(iri)
        return o.clazz(iri)
    typ_name = type(x).__name__
    if typ_name not in owltop.__dict__ and isinstance(x, type):
        for candidate in (Class, TopObjectProperty, DataProperty):
            if issubclass(x, candidate):
                if issubclass(x, Class):
                    return context.ontology.clazz(x.iri)
                if issubclass(x, TopObjectProperty):
                    # TODO: IRI
                    return context.ontology.object_property(x.__name__)
                if issubclass(x, DataPropertyProperty):
                    # TODO: IRI
                    return context.ontology.data_property(x.__name__)
        return context.ontology.clazz(x.__name__)
    if typ_name in owltop.__dict__:
        pho_cls = getattr(pyhornedowl.model, typ_name)
        kwargs = {}
        for k in vars(x):
            if not k.startswith("__"):
                v = getattr(x, k)
                kwargs[k] = rev_tr(v, context)
        # args = list(kwargs.values())
        return pho_cls(**kwargs)

    raise ValueError(f"Unknown type: {type(x)} for {x}")


def theory_to_py_indexed_ontology(theory: Theory) -> pyhornedowl.PyIndexedOntology:
    """
    Convert the PyOwl ontology to PHO.

    This currently assumes that sentences are annotated with the OWL axiom

    :param theory:
    :return:
    """
    pho = pyhornedowl.PyIndexedOntology()
    pho.add_prefix_mapping("", "https://example.com/")
    context = ConversionContext(ontology=pho)
    for s in theory.sentences:
        if "owl_axiom" in s.annotations:
            pyowl_ax = s.annotations["owl_axiom"]
            ax = rev_tr(pyowl_ax, context)
            pho.add_axiom(ax)
    return pho




def owl_axioms_to_py_indexed_ontology(axioms: List[owltop.Axiom]) -> pyhornedowl.PyIndexedOntology:
    """
    Convert the owldl axioms to a horned-owl PyIndexedOntology.

    :param axioms:
    :return:
    """
    pho = pyhornedowl.PyIndexedOntology()
    context = ConversionContext(ontology=pho)
    for axiom in axioms:
        pho_axiom = rev_tr(axiom, context)




