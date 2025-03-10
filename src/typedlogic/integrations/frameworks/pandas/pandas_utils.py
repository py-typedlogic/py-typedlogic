"""
Utilities for working with pandas DataFrames.

TODO: Expand this further to allow DFs to be used where facts are expected.
"""
from typing import List, Optional

import pandas as pd

from typedlogic import Term
from typedlogic.extensions.probabilistic import ProbabilisticModel
from typedlogic.solver import Model


def as_dataframe(model: Model) -> pd.DataFrame:
    """
    Convert a model to a pandas DataFrame.

    :param model:
    :return:
    """
    rows = []
    if isinstance(model, ProbabilisticModel):
        for term, prob in model.term_probabilities.items():
            row = {"probability": prob, "predicate": term.predicate, **term.bindings}
            rows.append(row)
    else:
        for term in model.ground_terms:
            row = {"predicate": term.predicate, **term.bindings}
            rows.append(row)
    return pd.DataFrame(rows)


def dataframe_to_terms(
    df: "pd.DataFrame", predicate: Optional[str] = None, predicate_field: str = "predicate"
) -> List[Term]:
    """
    Convert a pandas DataFrame to a list of terms.

    Example:

        >>> from typedlogic.transformations import as_prolog
        >>> import pandas as pd
        >>> from typedlogic import Term
        >>> df = pd.DataFrame({
        ...     "predicate": ["HasChild", "HasChild", "HasChild"],
        ...     "subject": ["Alice", "Bob", "Charlie"],
        ...     "object": ["Bob", "Charlie", "David"]
        ... })
        >>> terms = dataframe_to_terms(df)
        >>> print(as_prolog(terms))
        haschild('Alice', 'Bob')
        haschild('Bob', 'Charlie')
        haschild('Charlie', 'David')


    :param df:
    :param predicate:
    :param predicate_field:
    :return:
    """
    terms = []
    for _, row in df.iterrows():
        if predicate:
            this_predicate = predicate
            bindings = row.to_dict()
        else:
            this_predicate = row[predicate_field]
            bindings = {k: v for k, v in row.items() if k != predicate_field}
        term = Term(this_predicate, bindings)
        terms.append(term)
    return terms
