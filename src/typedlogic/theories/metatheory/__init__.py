"""
An optional metatheory for reasoning about typedlogic theories.

The core data model carries light syntactic types: an argument declaration names a base
type or a defined type, and that is the whole of it. This package adds an *optional*
layer with a second-order flavour, without changing the core or introducing a second
formalism, by reifying a theory into ground facts and reasoning over those facts with
ordinary first-order rules.

Three pieces:

- :mod:`~typedlogic.theories.metatheory.vocabulary` -- predicates describing a theory:
  its signatures, its type definitions, and the shape of its rules.
- :mod:`~typedlogic.theories.metatheory.reflection` -- turns a
  :class:`~typedlogic.datamodel.Theory` into ground facts of that vocabulary.
- :mod:`~typedlogic.theories.metatheory.axioms` -- the rules that derive subtyping,
  variable types, type clashes, and unstratified negation. These are plain `@axiom`
  functions, so they run on any solver and can be extended by any user.

Usage:

    >>> from typedlogic import Theory
    >>> from typedlogic.datamodel import PredicateDefinition
    >>> theory = Theory(
    ...     name="people",
    ...     type_definitions={"PersonID": "str", "OrgID": "str"},
    ...     predicate_definitions=[PredicateDefinition("Person", {"id": "PersonID"})],
    ... )
    >>> check_theory(theory).ok
    True

"""

from typedlogic.theories.metatheory.check import CheckResult, Diagnostic, check_theory
from typedlogic.theories.metatheory.reflection import skipped_sentences, theory_to_facts

__all__ = [
    "CheckResult",
    "Diagnostic",
    "check_theory",
    "skipped_sentences",
    "theory_to_facts",
]
