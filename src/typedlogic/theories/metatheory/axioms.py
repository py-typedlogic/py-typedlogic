"""
Rules about types and rules, written as ordinary typedlogic axioms.

This module is the point of the whole exercise: type checking is not a Python pass that
walks a syntax tree, it is a logic program over the vocabulary in
:mod:`typedlogic.theories.metatheory.vocabulary`. It is loaded into a solver exactly as
any other theory, so it runs on whichever solver the user already has.

Two consequences follow. Type rules are *extensible* -- a project can add its own
`@axiom` over the same predicates and have it enforced alongside these. And the analysis
is not limited to sorts: :class:`~typedlogic.theories.metatheory.vocabulary.UnstratifiedNegation`
below is a property of the rule graph, derived by the same means.

Negation in the rules below is written ``-P(...)``, the Python surface's spelling of
negation as failure. This is not interchangeable with ``not P(...)``, which is classical
negation: a classically negated body literal is lifted into a head disjunction on the way
to a solver, and an answer-set solver may then satisfy the rule by choosing the negated
atom instead of the intended conclusion -- so a check written with ``not`` reports
whichever findings the chosen model happens to contain. Every diagnostic here needs
"cannot be derived", which is what ``-`` means.

The negation is also stratified: `TypeClash` negates `Compatible`, which never depends on
`TypeClash`, so a solver with stratified negation (for example Clingo) accepts the program
without further conditions.
"""

from typedlogic import axiom
from typedlogic.theories.metatheory.vocabulary import (
    ArgType,
    BaseType,
    BodyPredicate,
    Compatible,
    ConstantClash,
    ConstantPosition,
    Depends,
    DependsNegatively,
    HeadPredicate,
    NegatedBodyPredicate,
    PredicateDeclared,
    PredicateName,
    RuleID,
    SubTypeOf,
    TypeBase,
    TypeClash,
    TypeExists,
    TypeGrounded,
    TypeName,
    TypeUnionMember,
    UndeclaredPredicate,
    UnstratifiedNegation,
    VarName,
    VarPosition,
    VarType,
)

# --- The subtype lattice -------------------------------------------------------------


@axiom
def subtype_reflexivity(t: TypeName):
    """Every type is assignable to itself, so a variable may meet the same type twice."""
    if TypeExists(t):
        assert SubTypeOf(t, t)


@axiom
def subtype_from_base(t: TypeName, b: TypeName):
    """A defined type is assignable to the base type it specializes."""
    if TypeBase(t, b):
        assert SubTypeOf(t, b)


@axiom
def subtype_from_union_member(u: TypeName, m: TypeName):
    """A member of a union is assignable to the union."""
    if TypeUnionMember(u, m):
        assert SubTypeOf(m, u)


@axiom
def subtype_transitivity(a: TypeName, b: TypeName, c: TypeName):
    """Assignability composes."""
    if SubTypeOf(a, b) and SubTypeOf(b, c):
        assert SubTypeOf(a, c)


@axiom
def base_types_are_grounded(t: TypeName):
    """A primitive type grounds itself."""
    if BaseType(t):
        assert TypeGrounded(t)


@axiom
def grounded_through_base(t: TypeName, b: TypeName):
    """A type is grounded if what it specializes is grounded."""
    if TypeBase(t, b) and TypeGrounded(b):
        assert TypeGrounded(t)


@axiom
def grounded_through_union(u: TypeName, m: TypeName):
    """A union is grounded once any member of it is."""
    if TypeUnionMember(u, m) and TypeGrounded(m):
        assert TypeGrounded(u)


@axiom
def compatible_by_assignability(left: TypeName, right: TypeName):
    """Two types are compatible if either is assignable to the other.

    Compatibility is deliberately weaker than equality: a variable may legitimately
    range over a position declared ``PersonID`` and one declared ``str``.
    """
    if SubTypeOf(left, right):
        assert Compatible(left, right)
        assert Compatible(right, left)


@axiom
def opaque_types_constrain_nothing(left: TypeName, right: TypeName):
    """An opaque type is compatible with everything, because nothing is known about it.

    Without this the checker would report incompatibility purely from its own ignorance:
    a type it cannot resolve to a base type would appear to conflict with every other
    type, turning every enum and every unreduced annotation into a false positive.
    """
    if TypeExists(left) and TypeExists(right) and -TypeGrounded(left):
        assert Compatible(left, right)
        assert Compatible(right, left)


# --- Typing the variables of a rule --------------------------------------------------


@axiom
def var_type_from_occurrence(rule: RuleID, var: VarName, p: PredicateName, i: int, t: TypeName):
    """Each occurrence of a variable constrains it to the type declared at that position."""
    if VarPosition(rule, var, p, i) and ArgType(p, i, t):
        assert VarType(rule, var, t)


@axiom
def type_clash(rule: RuleID, var: VarName, left: TypeName, right: TypeName):
    """A variable constrained to two incompatible types cannot be satisfied as declared.

    This is the check that a Souffle-style declaration alone cannot make: it is about a
    variable's occurrences *across* the literals of a rule, not about one signature.
    """
    if VarType(rule, var, left) and VarType(rule, var, right) and -Compatible(left, right):
        assert TypeClash(rule, var, left, right)


@axiom
def constant_clash(rule: RuleID, p: PredicateName, i: int, declared: TypeName, actual: TypeName):
    """A literal must be compatible with the type declared at the position it fills."""
    if ConstantPosition(rule, actual, p, i) and ArgType(p, i, declared) and -Compatible(actual, declared):
        assert ConstantClash(rule, p, i, declared, actual)


@axiom
def undeclared_head_predicate(rule: RuleID, p: PredicateName):
    """A rule deriving an undeclared predicate escapes every signature check."""
    if HeadPredicate(rule, p) and -PredicateDeclared(p):
        assert UndeclaredPredicate(rule, p)


@axiom
def undeclared_body_predicate(rule: RuleID, p: PredicateName):
    """A rule reading an undeclared predicate is reading a relation nothing populates."""
    if BodyPredicate(rule, p) and -PredicateDeclared(p):
        assert UndeclaredPredicate(rule, p)


# --- Properties of the rule graph ----------------------------------------------------


@axiom
def depends_positively(rule: RuleID, head: PredicateName, body: PredicateName):
    """A rule makes its head depend on each predicate in its body."""
    if HeadPredicate(rule, head) and BodyPredicate(rule, body):
        assert Depends(head, body)


@axiom
def depends_through_negation(rule: RuleID, head: PredicateName, body: PredicateName):
    """A negated body literal is a dependency, and a negative one."""
    if HeadPredicate(rule, head) and NegatedBodyPredicate(rule, body):
        assert Depends(head, body)
        assert DependsNegatively(head, body)


@axiom
def depends_transitivity(a: PredicateName, b: PredicateName, c: PredicateName):
    """Dependency composes."""
    if Depends(a, b) and Depends(b, c):
        assert Depends(a, c)


@axiom
def negative_dependency_is_absorbing(a: PredicateName, b: PredicateName, c: PredicateName):
    """A path is negative if any edge along it is negative."""
    if DependsNegatively(a, b) and Depends(b, c):
        assert DependsNegatively(a, c)
    if Depends(a, b) and DependsNegatively(b, c):
        assert DependsNegatively(a, c)


@axiom
def unstratified_negation(p: PredicateName):
    """A predicate that negatively depends on itself has no unique least model."""
    if DependsNegatively(p, p):
        assert UnstratifiedNegation(p)
