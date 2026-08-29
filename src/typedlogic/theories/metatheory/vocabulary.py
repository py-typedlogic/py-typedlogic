"""
Vocabulary for talking about a theory as data.

Every predicate here describes some part of a *object-level* theory: its predicate
signatures, its type definitions, and the shape of its rules. A theory reflected into
this vocabulary (see :mod:`typedlogic.theories.metatheory.reflection`) becomes an
ordinary set of ground facts, so rules *about* types are ordinary first-order rules --
second-order in flavour, first-order in machinery, and runnable on any existing solver.

The vocabulary is split in two:

- **Asserted** predicates are produced by the reflector, and describe the theory as
  written: :class:`ArgType`, :class:`TypeBase`, :class:`VarPosition`, and so on.
- **Derived** predicates are computed by the axioms in
  :mod:`typedlogic.theories.metatheory.axioms`: :class:`SubTypeOf`, :class:`VarType`,
  :class:`TypeClash`, :class:`UnstratifiedNegation`, and so on.

Nothing here is privileged. A user who wants a rule the built-in axioms do not provide
-- say, that an argument declared ``PersonID`` may never meet one declared ``OrgID`` --
writes it as an `@axiom` over these predicates rather than patching Python.
"""

from dataclasses import dataclass
from typing import NewType

from typedlogic import Fact

#: The name of a type: either a base type (``str``, ``int``) or a defined type.
TypeName = NewType("TypeName", str)

#: The name of a predicate in the object theory.
PredicateName = NewType("PredicateName", str)

#: An identifier for one rule of the object theory, used to scope variable names.
RuleID = NewType("RuleID", str)

#: The name of a variable, unique only within its rule.
VarName = NewType("VarName", str)


# --- Asserted by the reflector -------------------------------------------------------


@dataclass(frozen=True)
class TypeExists(Fact):
    """A type is mentioned somewhere in the theory.

    Supplies the domain that reflexive rules such as ``SubTypeOf(t, t)`` range over.
    """

    type: TypeName


@dataclass(frozen=True)
class BaseType(Fact):
    """A primitive type, at the bottom of every chain of type definitions."""

    type: TypeName


@dataclass(frozen=True)
class TypeBase(Fact):
    """A defined type specializes a base type, as ``PersonID = NewType("PersonID", str)``."""

    type: TypeName
    base: TypeName


@dataclass(frozen=True)
class TypeUnionMember(Fact):
    """A union type admits a member type, as ``Key = Union[str, int]``."""

    type: TypeName
    member: TypeName


@dataclass(frozen=True)
class ArgType(Fact):
    """An argument position of a predicate is declared to hold a given type."""

    predicate: PredicateName
    position: int
    type: TypeName


@dataclass(frozen=True)
class PredicateDeclared(Fact):
    """The theory declares a signature for this predicate."""

    predicate: PredicateName


@dataclass(frozen=True)
class ArgName(Fact):
    """An argument position of a predicate carries a given name.

    Kept separate from :class:`ArgType` so that rules about types need not bind a name
    they do not use.
    """

    predicate: PredicateName
    position: int
    name: str


@dataclass(frozen=True)
class PredicateParent(Fact):
    """A predicate is declared as a specialization of another, as by Python inheritance."""

    child: PredicateName
    parent: PredicateName


@dataclass(frozen=True)
class VarPosition(Fact):
    """Within a rule, a variable occurs at an argument position of a predicate.

    A variable occurring at two positions is what makes the two positions' declared types
    meet, and hence what a type clash is computed from.
    """

    rule: RuleID
    var: VarName
    predicate: PredicateName
    position: int


@dataclass(frozen=True)
class ConstantPosition(Fact):
    """Within a rule, a literal of a given base type occurs at a position of a predicate."""

    rule: RuleID
    base_type: TypeName
    predicate: PredicateName
    position: int


@dataclass(frozen=True)
class HeadPredicate(Fact):
    """A rule derives the given predicate."""

    rule: RuleID
    predicate: PredicateName


@dataclass(frozen=True)
class BodyPredicate(Fact):
    """A rule's body positively references the given predicate."""

    rule: RuleID
    predicate: PredicateName


@dataclass(frozen=True)
class NegatedBodyPredicate(Fact):
    """A rule's body references the given predicate under a negation."""

    rule: RuleID
    predicate: PredicateName


# --- Derived by the axioms -----------------------------------------------------------


@dataclass(frozen=True)
class SubTypeOf(Fact):
    """A value of ``sub`` is acceptable wherever ``sup`` is expected.

    Reflexive and transitive; the reflexive case is what lets a type meet itself without
    being reported as a clash.
    """

    sub: TypeName
    sup: TypeName


@dataclass(frozen=True)
class TypeGrounded(Fact):
    """A type resolves, through its definitions, to a base type.

    A type that does not -- an enum class, or a name left over from an annotation the
    Python introspector could not reduce, such as ``Optional`` -- is *opaque*: the
    metatheory knows nothing about what it admits, and so must not claim any
    incompatibility for it.
    """

    type: TypeName


@dataclass(frozen=True)
class Compatible(Fact):
    """One type is assignable to the other in some direction, so a variable may span both.

    Also holds whenever either side is opaque, because an unprovable incompatibility must
    not be reported as one.
    """

    left: TypeName
    right: TypeName


@dataclass(frozen=True)
class VarType(Fact):
    """A variable is constrained to a type by one of its occurrences.

    A variable used at several positions gets one `VarType` per position; the useful
    question is whether they agree.
    """

    rule: RuleID
    var: VarName
    type: TypeName


@dataclass(frozen=True)
class TypeClash(Fact):
    """A variable is used at two positions whose declared types are not compatible."""

    rule: RuleID
    var: VarName
    left: TypeName
    right: TypeName


@dataclass(frozen=True)
class ConstantClash(Fact):
    """A literal appears at a position whose declared type cannot hold it."""

    rule: RuleID
    predicate: PredicateName
    position: int
    declared: TypeName
    actual: TypeName


@dataclass(frozen=True)
class UndeclaredPredicate(Fact):
    """A rule references a predicate that the theory never declares."""

    rule: RuleID
    predicate: PredicateName


@dataclass(frozen=True)
class Depends(Fact):
    """A predicate depends on another, directly or transitively, through some rule."""

    head: PredicateName
    body: PredicateName


@dataclass(frozen=True)
class DependsNegatively(Fact):
    """A predicate's dependency on another passes through at least one negation."""

    head: PredicateName
    body: PredicateName


@dataclass(frozen=True)
class UnstratifiedNegation(Fact):
    """A predicate lies on a recursive cycle that passes through a negation.

    Such a program has no unique least model, so this is a property of the *rules* rather
    than of any sort -- and it falls out of the same machinery.
    """

    predicate: PredicateName
