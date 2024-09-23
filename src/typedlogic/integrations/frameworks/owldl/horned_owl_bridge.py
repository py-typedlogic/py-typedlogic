import types
from typing import Any, List, Dict

from typedlogic.integrations.frameworks.owldl import Thing, TopDataProperty, TopObjectProperty, Ontology
import typedlogic.integrations.frameworks.owldl.owltop as owltop

#import pyhornedowl
from pyhornedowl import DataPropertyAssertion  # type: ignore
#import pyhornedowl.model as phm  # type: ignore
from rdflib import RDFS

def load_ontology(source: str) -> List[owltop.Axiom]:
    """
    Load the ontology.

    :param ontology:
    :return:
    """
    onto = pyhornedowl.open_ontology(str(source))
    sentences = pho_to_pyowl(onto)
    return sentences


def pho_to_pyowl(ontology: pyhornedowl.PyIndexedOntology) -> List[owltop.Axiom]:
    """
    Convert the PHO ontology to PyOwl.

    :param ontology:
    :return:
    """
    axioms: List[owltop.Axiom] = []
    label_map = {}
    for oc in ontology.get_axioms():
        a = oc.component
        if isinstance(a, phm.AnnotationAssertion):
            ann = a.ann
            ap = ann.ap
            if str(ap.first) == str(RDFS.label):
                if isinstance(ann.av, (phm.SimpleLiteral, phm.LanguageLiteral, phm.DatatypeLiteral)):
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

def tr(x: Any, label_map: Dict[str, str], parent=None) -> Any:
    """
    Translate the axiom.

    :param x:
    :return:
    """
    if isinstance(x, list):
        return [tr(i, label_map) for i in x]
    if isinstance(x, phm.IRI):
        return str(x)
    if isinstance(x, phm.NamedIndividual):
        return str(x.first)
    if isinstance(x, (phm.Class, phm.ObjectProperty, phm.DataProperty)):
        if isinstance(x, phm.Class):
            superclass = Thing
        elif isinstance(x, phm.ObjectProperty):
            superclass = TopObjectProperty
        elif isinstance(x, phm.DataProperty):
            superclass = TopDataProperty

        entity_iri = str(x.first)
        def class_body(namespace):
            namespace["iri"] = entity_iri
        entity_lbl = label_map.get(entity_iri, entity_iri)
        if entity_lbl.startswith("http"):
            entity_lbl = entity_lbl.split("/")[-1]
        # replace any non alpha-numeric characters with _
        entity_lbl = "".join([c if c.isalnum() else "_" for c in entity_lbl])
        # entity_lbl = entity_lbl.replace("#", "_").replace(":", "_")
        py_cls = types.new_class(entity_lbl, (superclass,), {}, class_body)
        py_cls.__module__ = "__temp__"
        return py_cls
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


