from typing import Type

import typedlogic.integrations.frameworks.linkml.instance as inst
import typedlogic.integrations.frameworks.linkml.loader as linkml_loader
import typedlogic.theories.jsonlog.loader as jsonlog_loader
from typedlogic import Theory
from typedlogic.solver import Solver


def validate(schema: dict, data: dict, solver_class: Type[Solver]) -> bool:
    """
    Validate a JSON object against a LinkML schema using a specified solver.

    :param schema:
    :param data:
    :param solver_class:
    :return:
    """
    theory = Theory()
    theory.extend(linkml_loader.generate_from_object(schema))
    theory.extend(jsonlog_loader.generate_from_object(data))
    solver = solver_class()
    solver.add(theory)
    return not not solver.check().satisfiable