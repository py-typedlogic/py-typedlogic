from typedlogic.integrations.frameworks.owldl import (
    Thing,
    TopObjectProperty,
)


class Person(Thing):
    """A person, living or dead."""
    pass

class HasParent(TopObjectProperty):
    """A property that relates a person to their parent."""
    domain = Person
    range = Person

class HasChild(TopObjectProperty):
    """A property that relates a person to their child."""
    inverse_of = HasParent