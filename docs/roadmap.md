# Roadmap

## Solvers

Add solvers for the following:

- dlv
- vampire
- OWL Reasoners (via owlery, robot, or py-horned-owl)
- problog

## Framework Integrations

- OWL, using py-horned-owl
- LinkML

## Transformations

Add other useful transformations, e.g NNF

## Documentation

- document differences with HETS, DOL

## Current Limitations

### Nested objects

In Python data models it's common to have something like:

```python
class Address(BaseModel):
    street: str
    city: str
    state: str

class Person(BaseModel):
    name: str
    addresses: List[Address]
```

Which assumes nested data objects, typically serialized as YAML/JSON.

Currently typedlogic forces you to model in *Normal Form*, for example:

```python
class Address(BaseModel):
    id: str
    address_street: str
    address_city: str
    address_state: str

    
class Person(BaseModel):
    name: str

class PersonAddress(BaseModel):
    person_name: str
    address_id: str
```

This is more typical of how you would model things with SQLModel or SQLAlchemy classes that are isomorphic to SQL tables.

The corresponding instances (ground terms) would not involve any nesting.

In the future, we would like to do this normalization on the fly, AND/OR something analogous to JSONB in Postgresql.