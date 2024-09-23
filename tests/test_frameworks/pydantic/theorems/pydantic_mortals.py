# Example usage
from typing import Union

from pydantic import BaseModel, Field
from typedlogic import FactMixin, gen, axiom
from typedlogic.integrations.frameworks.pydantic import FactBaseModel

ID = str

IntOrFloat= Union[int, float]

class Person(BaseModel, FactMixin):
    name: ID = Field(..., description="unique name")

class AncestorOf(FactBaseModel):
    ancestor: ID = Field(..., description="name of ancestor")
    descendant: ID = Field(..., description="name of descendant")

class PersonAge(FactBaseModel):
    person: ID = Field(..., description="unique name of person")
    age: int = Field(..., ge=0)

class PersonHeight(FactBaseModel):
    person: ID = Field(..., description="unique name of person")
    height: Union[int, float] = Field(..., description="height in cm")

class PersonHeight2(FactBaseModel):
    person: ID = Field(..., description="unique name of person")
    height: IntOrFloat = Field(..., description="height in cm")

@axiom
def axioms():
    all(
        AncestorOf(ancestor=x, descendant=y)
        for x, y, z in gen(str, str, str)
        if AncestorOf(ancestor=x, descendant=z) & AncestorOf(ancestor=z, descendant=y)
    )
