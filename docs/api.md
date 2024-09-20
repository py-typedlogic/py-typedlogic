# api_reference.md

# API Reference


This page provides a detailed reference for the main classes and functions in TypedLogic.

## Core Classes

### `FactMixin`

Base mixin class for defining facts.

### `Theory`

Represents a collection of predicate definitions, facts, and axioms.

**Attributes:**
- `name: Optional[str]`
- `constants: Dict[str, Any]`
- `type_definitions: Dict[str, Any]`
- `predicate_definitions: List[PredicateDefinition]`
- `sentence_groups: List[SentenceGroup]`
- `ground_terms: List[Term]`

### `PredicateDefinition`

Defines a predicate with its arguments and types.

**Attributes:**
- `predicate: str`
- `arguments: Dict[str, Any]`
- `description: Optional[str]`
- `metadata: Optional[Dict[str, Any]]`
- `parents: Optional[List[str]]`

### `Sentence`

Base class for logical sentences.

### `Term`

Represents a logical term (predicate application).

## Decorators

### `@axiom`

Decorator for defining axioms as Python functions.

## Functions

### `gen1(type1: Type[T1]) -> Generator[T1, None, None]`

Generate a single typed variable.

### `gen2(type1: Type[T1], type2: Type[T2]) -> Generator[Tuple[T1, T2], None, None]`

Generate a pair of typed variables.

### `gen3(type1: Type[T1], type2: Type[T2], type3: Type[T3]) -> Generator[Tuple[T1, T2, T3], None, None]`

Generate a triple of typed variables.

## Solvers

### `Z3Solver`

Solver implementation using Z3.

### `SouffleSolver`

Solver implementation using Souffle.

## Logical Operators

- `And`: Logical AND
- `Or`: Logical OR
- `Not`: Logical NOT
- `Implies`: Logical implication
- `Iff`: Logical equivalence
- `Forall`: Universal quantification
- `Exists`: Existential quantification

This API reference provides an overview of the main components of TypedLogic. For more detailed information on each class and function, including method signatures and usage examples, please refer to the inline documentation in the source code.

