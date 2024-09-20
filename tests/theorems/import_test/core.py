from pydantic import BaseModel
from typedlogic import FactMixin

ID = str

class NamedThing(BaseModel, FactMixin):
    name: ID

class Relationship(BaseModel, FactMixin):
    subject: ID
    predicate: ID
    object: ID
