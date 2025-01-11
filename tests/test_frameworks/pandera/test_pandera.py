from enum import Enum
from itertools import groupby

import pandas as pd
import pandera as pa
import pytest
from pandera.typing import DataFrame

from typedlogic import axiom, Term, Variable, Theory, PredicateDefinition
from typedlogic.integrations.frameworks.pandas.pandas_utils import dataframe_to_terms
from typedlogic.registry import get_solver


class Unit(str, Enum):
    Cel = "Cel"
    K = "K"
    ug_per_m3 = "ug/m3"

class Site(pa.DataFrameModel):
    """
    Pandera schema for sites
    """
    name: str = pa.Field(coerce=True)
    country: str = pa.Field(coerce=True)

class Observation(pa.DataFrameModel):
    """
    Pandera schema for generic observations
    """
    val: float = pa.Field(coerce=True)
    quantity: str = pa.Field(coerce=True)
    unit: str = pa.Field(coerce=True)
    site: str = pa.Field(coerce=True)
    year: int = pa.Field(ge=1900,coerce=True)

class AverageTemperature(pa.DataFrameModel):
    """
    Pandera schema for average temperature observations by site.
    """
    temp_c: float = pa.Field()
    site: str = pa.Field(coerce=True)

class HighTemperature(AverageTemperature):
    """
    Pandera schema for high average temperature observations by site.
    """

@pa.check_types
def transform(df: DataFrame[Observation]) -> DataFrame[AverageTemperature]:
    """
    Transform a dataframe of observations into a dataframe of average temperatures.

    :param df:
    :return:
    """
    temp_df = df[
        (df[Observation.unit] == Unit.Cel.value) &
        (df[Observation.quantity] == "temperature")  # or whatever your temperature quantity identifier is
        ]
    result = (temp_df
              .groupby(Observation.site)
              [Observation.val]  # specify just the value column
              .mean()
              .reset_index()
              .rename(columns={Observation.val: AverageTemperature.temp_c}))
    return DataFrame[AverageTemperature](result)

# def bad_mypy(df: DataFrame[Observation]) -> DataFrame[Observation]:
#     """
#     This is a bad function that returns the wrong type.
#
#     TODO: this should be caught by mypy.
#
#     :param df:
#     :return:
#     """
#     return df.assign(foo=100).pipe(DataFrame[AverageTemperature])

@axiom
def entail_high_temps(temp_c: float, site: str):
    # TODO: change this, this is highly non idiomatic, and syntactically incorrect
    if AverageTemperature(temp_c=temp_c, site=site):
        return HighTemperature(temp_c=temp_c, site=site)

#def entail_high_temps2(df: DataFrame[AverageTemperature]) -> DataFrame[HighTemperature]:
#    df.query("temp_c > 30").pipe(DataFrame[HighTemperature])

@pytest.fixture
def example_observation_data() -> DataFrame[Observation]:
    """
    Example data for testing.

    :return:
    """
    df = pd.DataFrame({
        "val": [80.0, 82.0, 5.0],
        "quantity": ["temperature", "temperature", "pm2.5"],
        "unit": [Unit.Cel, Unit.Cel, Unit.ug_per_m3],
        "site": ["ABC", "ABC", "ABC"],
        "year": [2001, 2002, 2001],
    })
    return DataFrame[Observation](df)

def test_validate_pandera(example_observation_data: DataFrame[Observation]):
    """
    Test the pandera schema.

    TODO: so far this does not actually check any logical aspects.

    :return:
    """

    tr = transform(example_observation_data)
    # print(tr)

    invalid_df = pd.DataFrame({
        "val": [80.0, 82.0, 5.0],
        "quantity": ["temperature", "temperature", "pm2.5"],
        "unit": ["Cel", "Cel", "ug/m3"],
        "site": ["ABC", "ABC", "ABC"],
        "year": ["1899", "2002", "2001"],
    })

    with pytest.raises(pa.errors.SchemaError):
        transform(invalid_df) # type: ignore

    x = Variable("x")
    y = Variable("y")
    sentence = Term(AverageTemperature.__name__, x, y) >> Term(HighTemperature.__name__, x, y)
    print(sentence)
    theory = Theory()
    theory.add(sentence)
    solver = get_solver("clingo")
    solver.add_predicate_definition(PredicateDefinition(AverageTemperature.__name__, {"temp_c": "float", "site": "str"}))
    solver.add_theory(theory)
    terms = dataframe_to_terms(tr, predicate=AverageTemperature.__name__)
    solver.add(terms)
    print("Dumping solver:")
    print(solver.dump())
    models = list(solver.models())
    print(models)


def test_pandera_bridge():
    """
    Test the pandera schema.

    TODO: so far this does not actually check any logical aspects.

    :return:
    """
    pass