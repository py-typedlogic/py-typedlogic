from typedlogic.integrations.frameworks.pydantic import FactBaseModel
from pydantic import Field

class Person(FactBaseModel):
    name: str = Field(..., description="unique name of the person")
    age: int = Field(..., description="age in years", ge=0)