from typing import List

from typedlogic import PredicateDefinition, Term
from typedlogic.datamodels.typesystem import get_python_type


def make_terms(rows: List[List[str]], pd: PredicateDefinition) -> List[Term]:
    """
    Make terms from a list of rows

    Example:
    
        >>> pd = PredicateDefinition("FriendOf", {"person": "str", "friend": "str"})
        >>> make_terms([["Amy", "Zardoz"], ["Zardoz", "John"]], pd)
        [FriendOf(Amy, Zardoz), FriendOf(Zardoz, John)]

    """
    terms = []
    for i, pd_arg in enumerate(pd.arguments.values()):
        py_type = get_python_type(pd_arg)
        if not py_type:
            continue
        if py_type == str:
            continue
        for j, row in enumerate(rows):
            rows[j][i] = py_type(row[i])
    pred = pd.predicate
    for row in rows:
        if not pd.arguments:
            terms.append(Term(pred))
        else:
            # TODO: coerce ints
            terms.append(Term(pred, *row))
    return terms
