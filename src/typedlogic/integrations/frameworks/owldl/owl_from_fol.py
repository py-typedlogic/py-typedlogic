from typing import Iterator, Union, List, Tuple, Type, Optional, Any

from typedlogic import Theory, Forall, Implies, Sentence, Term, Variable
from typedlogic.integrations.frameworks.owldl import SubClassOf
from typedlogic.integrations.frameworks.owldl.owltop import (
    Axiom,
    ClassExpression,
    ObjectPropertyExpression,
    OntologyElement,
    Class,
    AnonymousClassExpression,
)


def axioms_from_theory(theory: Union[Theory, List[Sentence]]) -> Iterator[Axiom]:
    """
    Translates a FOL theory into OWL axioms.

    .. warning:: TODO: highly incomplete

    Example:

        >>> x = Variable("x")
        >>> for a in axioms_from_theory([Term("C", x) >> Term("D", x)]):
        ...     print(a)
        SubClassOf(C, D)

    :param theory: a Theory object or a list of sentences
    :return: an iterator of OWL axioms
    """
    if isinstance(theory, list):
        sentences = theory
        theory = Theory()
        for s in sentences:
            theory.add(s)
    for s in theory.sentences:
        if isinstance(s, Forall):
            vars = s.variables
            body = s.sentence
        else:
            body = s
            vars = []
        if isinstance(body, Implies):
            lhs = to_expression(body.antecedent)
            rhs = to_expression(body.consequent)
            if lhs and rhs:
                lhs_ce = as_class_expression(lhs)
                rhs_ce = as_class_expression(rhs)
                if lhs_ce and rhs_ce:
                    if lhs[1] == rhs[1]:
                        if not vars or vars == lhs[1]:
                            yield SubClassOf(lhs_ce, rhs_ce)
    return None


def as_class_expression(x: Optional[Tuple[Any, Any]]) -> Optional[ClassExpression]:
    if x is None:
        return None
    x = x[0]
    if isinstance(x, (str, AnonymousClassExpression, OntologyElement)):
        return x
    return None


def to_expression(
    sentence: Sentence,
) -> Optional[Tuple[Union[ClassExpression, ObjectPropertyExpression], List[Variable]]]:
    """
    ...

    Example:

       >>> x = Variable("x")
       >>> to_expression(Term("C", x))
       (Class(C), [Variable(name='x', domain=None, constraints=None)])

    :param sentence:
    :return:
    """
    if isinstance(sentence, Term):
        if len(sentence.values) == 1:
            term_vars = sentence.variables
            if len(term_vars) == 1:
                return OntologyElement(sentence.predicate, "Class"), term_vars
        if len(sentence.values) == 2:
            term_vars = sentence.variables
            if len(term_vars) == 2:
                return OntologyElement(sentence.predicate, "Property"), term_vars
    return None
