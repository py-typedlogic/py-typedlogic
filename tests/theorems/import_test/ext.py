from tests.theorems.import_test import NamedThing, Relationship


class Person(NamedThing):
    age: int

class Likes(Relationship):
    reciprocated: bool
