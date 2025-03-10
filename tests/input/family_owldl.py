from typedlogic.integrations.frameworks.owldl import SubObjectPropertyOf, Thing, TopObjectProperty


class Person(Thing):
    """A person, living or dead."""

    pass


class HasAncestor(TopObjectProperty):
    """A property that relates a person to their parent."""


class HasDescendant(TopObjectProperty):
    """A property that relates a person to their child."""

    transitive = True
    asymmetric = True


class HasParent(HasAncestor):
    """A property that relates a person to their parent."""

    domain = Person
    range = Person


class HasChild(HasDescendant):
    """A property that relates a person to their child."""

    inverse_of = HasParent


__axioms__ = [SubObjectPropertyOf(HasParent, HasAncestor), SubObjectPropertyOf(HasChild, HasDescendant)]
