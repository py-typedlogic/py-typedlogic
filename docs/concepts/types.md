# Typing in typed-logic

Broadly speaking, logics can be broken down into *untyped* logics, and *typed* (also known as *sorted*) logics.

The data model for typedlogic follows the typed logic model. Typing operates at three
levels, which are worth keeping distinct.

## 1. The Python surface

Any typed-logic theory written in Python follows the same rules as the rest of Python.
It must of course be a valid Python program, without any syntax or runtime errors.

Additionally, you can avail yourself of standard Python tooling to help keep your code clean
and bug-free. This includes type checking, whether via a tool such as `mypy`, or simply
via your IDE. This is *prescriptive* typing: you declare, and code that disagrees is
rejected.

## 2. The theory's own type declarations

A [`Theory`][typedlogic.datamodel.Theory] carries `type_definitions` mapping a name to a
base type or a union of them, and each `PredicateDefinition` declares a type per argument.
This is a light, Souffle-style layer, and it is what typed targets consume.

Note that Python erases plain aliases before they can be introspected:

```python
PersonID = str          # erased; never reaches the logic
PersonID = NewType("PersonID", str)   # survives, and brands the argument
```

Only `NewType` (or an explicit `type` declaration in [TLog](../conversion/parsers/tlog.md))
carries a distinct type *name* through to the compiled output. With `NewType`, a branded
type compiles to a Souffle subtype:

```
.type PersonID <: symbol
.decl parent(parent: PersonID, child: PersonID)
```

The `<:` matters. Souffle's `.type PersonID = symbol` defines an *alias*, under which
`PersonID` and `OrgID` remain mutually assignable; `<:` defines a genuine subtype that
Souffle enforces.

!!! note

    A branded type over `number` that takes part in arithmetic needs alias semantics,
    because Souffle types the result of an arithmetic functor as `number`, which is not a
    subtype of the branded type. Use `SouffleCompiler(strict_subtypes=False)` in that case.

## 3. The optional metatheory

Declarations alone cannot express properties that span a rule — that one variable is used
at two incompatible argument positions, or that a rule set recurses through negation. The
optional [metatheory](metatheory.md) covers these by reifying a theory into ground facts
and reasoning over them with ordinary axioms, so type rules are themselves logic and can
be extended by the user.
