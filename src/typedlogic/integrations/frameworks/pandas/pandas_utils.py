import pandas as pd

from typedlogic.extensions.probabilistic import ProbabilisticModel
from typedlogic.solver import Model


def as_dataframe(model: Model) -> pd.DataFrame:
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
