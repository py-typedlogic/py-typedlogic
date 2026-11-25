from typing import Any, List

from typedlogic import PredicateDefinition, Term
from typedlogic.datamodels.typesystem import get_python_type


def make_terms(rows: List[List[Any]], pd: PredicateDefinition) -> List[Term]:
    """
    Make terms from a list of rows

    Example:
    
        >>> pd = PredicateDefinition("FriendOf", {"person": "str", "friend": "str"})
        >>> make_terms([["Amy", "Zardoz"], ["Zardoz", "John"]], pd)
        [FriendOf(Amy, Zardoz), FriendOf(Zardoz, John)]

    Values are coerced to the declared argument types:

        >>> pd = PredicateDefinition("Flag", {"name": "str", "n": "int", "on": "bool"})
        >>> [t.values for t in make_terms([["a", "1", "true"], ["b", "2", "false"]], pd)]
        [('a', 1, True), ('b', 2, False)]

    """
    terms = []
    for i, pd_arg in enumerate(pd.arguments.values()):
        py_type = get_python_type(pd_arg)
        if not py_type:
            continue
        if py_type == str:
            continue
        for j, row in enumerate(rows):
            if py_type == bool:
                # bool("false") is True; booleans are serialized as true/false
                rows[j][i] = str(row[i]).lower() == "true"
            else:
                rows[j][i] = py_type(row[i])
    pred = pd.predicate
    for row in rows:
        if not pd.arguments:
            terms.append(Term(pred))
        else:
            # TODO: coerce ints
            terms.append(Term(pred, *row))
    return terms
