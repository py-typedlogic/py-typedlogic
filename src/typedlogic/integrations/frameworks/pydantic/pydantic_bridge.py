from pydantic import BaseModel

from typedlogic import Fact


class FactBaseModel(BaseModel, Fact):
    """
    A Pydantic BaseModel that mixes in typed-logic Fact.

    You can use this class instead of Pydantic `BaseModel`, it will map your class onto a
    `PredicateDefinition`.

    Additionally, it allows for positional arguments, which is not the default in Pydantic.

    Example:
    -------
    ```python
    class PersonAge(FactBaseModel):
        name: str
        age: int
    ```

    This creates a PredicateDefinition for a two-place (arity=2) predicate relating a person to
    their age.

    This can be instantiated positionally:

    ```python
    pa1 = PersonAge("Akira", 33)
    ```

    Or with keywords:

    ```python
    pa1 = PersonAge(name="Akira", age=33)
    ```

    This inherits from `Fact`, which means that these can be used as ground terms in a theory.
    To convert the domain instance to a generic object, using `to_model_object`

    ```python
    assert PersonAge(name="Akira", age=33).to_model_object() == Term("PersonAge", "Akira", 33)
    ```

    ## Limitations

    We currently use Pydantic's `model_json_schema()` to convert a pydantic model to JSON-Schema to
    extract type metadata, but this is currently lossy. You may find that your types are
    converted to strings.


    """

    def __init__(self, *args, **kwargs):
        if args:
            kwargs.update(zip(self.model_fields, args, strict=False))
        super().__init__(**kwargs)
