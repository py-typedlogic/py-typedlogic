"""
A project-specific rule written over the metatheory vocabulary.

Demonstrates that the built-in axioms are not privileged: a rule the framework does not
ship can be added as an ordinary `@axiom` and enforced alongside them, with no change to
the checker.

The rule here is a lint rather than a soundness property -- an argument declared as a
bare ``str`` was never branded, so nothing stops a person id from being used where an
organization id was meant.
"""

from dataclasses import dataclass

from typedlogic import Fact, axiom
from typedlogic.theories.metatheory.vocabulary import ArgType, PredicateName, TypeName

#: Referenced as a module constant rather than inline, so the rule stays a plain
#: comparison the axiom parser can read while keeping the declared type honest.
STRING_TYPE = TypeName("str")


@dataclass(frozen=True)
class UnbrandedArgument(Fact):
    """An argument position was declared with a base type rather than a branded one."""

    predicate: PredicateName
    position: int


@axiom
def flag_unbranded_string_arguments(p: PredicateName, i: int):
    """An argument declared as a bare string carries no brand to enforce."""
    if ArgType(p, i, STRING_TYPE):
        assert UnbrandedArgument(p, i)
