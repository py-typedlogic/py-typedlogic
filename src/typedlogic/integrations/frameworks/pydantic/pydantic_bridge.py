from pydantic import BaseModel

from typedlogic import Fact


class FactBaseModel(BaseModel, Fact):
    """
    A Pydantic BaseModel that mixes in typed-logic Fact
    """

    def __init__(self, *args, **kwargs):
        if args:
            kwargs.update(zip(self.model_fields, args, strict=False))
        super().__init__(**kwargs)
