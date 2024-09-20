from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar, Optional, Type, Union

from typedlogic import Sentence, Theory
from typedlogic.parser import Parser


class ModelSyntax(str, Enum):
    UNKNOWN = "unknown"
    SEXPR = "sexpr"
    FUNCTIONAL = "functional"


@dataclass
class Compiler(ABC):
    """
    An engine for compiling from the internal logical model representation to an external format.

    Note: one of the main use cases for compiling a theory is to generate an input for a solver.
    For many use cases, it's possible to just use a Solver directly, and let the system
    take care of compilation to an intermediate form.

    You can use the registry `get_compiler` method to get a compiler for a particular syntax:

        >>> from typedlogic.registry import get_compiler
        >>> compiler = get_compiler("fol")

    Next we will transpile from Python to FOL syntax. We will use a `Parser` object:

        >>> from typedlogic.registry import get_parser
        >>> parser = get_parser("python")
        >>> theory = parser.parse_file("tests/theorems/animals.py")

    Now we will compile the theory to FOL syntax:

        >>> print(compiler.compile(theory))
        Person('Fred')
        Person('Jie')
        Animal('corky', 'cat')
        Animal('fido', 'dog')
        ∀[x:Thing species:Thing]. Animal(x, species) → Likes(x, 'Fred')
        ∀[x:Thing species:Thing]. Animal(x, 'cat') → Likes(x, 'Jie')
        ∀[x:Thing species:Thing]. Animal(x, 'dog') → ¬Likes('Fred', x)

    Another useful syntax is TPTP, which is accepted by many theorom provers:

        >>> compiler = get_compiler("tptp")
        >>> print(compiler.compile(theory))
        % Problem: animals
        fof(axiom1, axiom, person('Fred')).
        fof(axiom2, axiom, person('Jie')).
        fof(axiom3, axiom, animal('corky', 'cat')).
        fof(axiom4, axiom, animal('fido', 'dog')).
        fof(axiom5, axiom, ! [X, Species] : (animal(X, Species) => likes(X, 'Fred'))).
        fof(axiom6, axiom, ! [X, Species] : (animal(X, 'cat') => likes(X, 'Jie'))).
        fof(axiom7, axiom, ! [X, Species] : (animal(X, 'dog') => ~likes('Fred', X))).

    Another common syntax is Prolog syntax, and its variants. These are often used by Datalog solvers:

        >>> compiler = get_compiler("prolog")
        >>> print(compiler.compile(theory))
        %% Predicate Definitions
        % Likes(subject: str, object: str)
        % Person(name: str)
        % Animal(name: str, species: str)
        <BLANKLINE>
        %% persons
        <BLANKLINE>
        person('Fred').
        person('Jie').
        <BLANKLINE>
        %% animals
        <BLANKLINE>
        animal('corky', 'cat').
        animal('fido', 'dog').
        <BLANKLINE>
        %% animal_preferences
        <BLANKLINE>
        likes(X, 'Fred') :- animal(X, Species).
        likes(X, 'Jie') :- animal(X, 'cat').
        <BLANKLINE>


    """

    default_suffix: ClassVar[str] = "txt"
    parser_class: ClassVar[Optional[Type[Parser]]] = None
    strict: Optional[bool] = None


    @abstractmethod
    def compile(self, theory: Theory, syntax: Optional[Union[str, ModelSyntax]] = None, **kwargs) -> str:
        """
        Compile a theory into an external representation.

        :param theory:
        :param syntax:
        :param kwargs:
        :return:
        """
        pass

    def compile_sentence(self, sentence: Sentence, syntax: Optional[Union[str, ModelSyntax]] = None, **kwargs) -> str:
        """
        Compiles an individual sentence

        :param sentence:
        :param syntax:
        :param kwargs:
        :return:
        """
        theory = Theory()
        theory.add(sentence)
        return self.compile(theory, syntax=syntax, **kwargs)

    @property
    def suffix(self) -> str:
        return self.default_suffix

    def _add_untranslatable(self, sentence: Sentence):
        pass
