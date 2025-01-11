from dataclasses import dataclass
from typing import ClassVar, Optional, Union

from typedlogic import Theory
from typedlogic.compiler import Compiler, ModelSyntax
from typedlogic.datamodel import NotInProfileError
from typedlogic.transformations import PrologConfig, as_fol, as_prolog


@dataclass
class PrologCompiler(Compiler):
    """A Compiler that generates Prolog code from a Theory object."""

    default_suffix: ClassVar[str] = "pro"
    config: Optional[PrologConfig] = None

    def compile(self, theory: Theory, syntax: Optional[Union[str, ModelSyntax]] = None, **kwargs) -> str:
        """
        Compile a Theory object into Prolog code.

        Example:
        -------
            >>> from typedlogic import *
            >>> theory = Theory()
            >>> x = Variable("x")
            >>> theory.predicate_definitions = [PredicateDefinition("P", {"x": "str"}),
            ...              PredicateDefinition("Q", {"x": "str"})]
            >>> s = Implies(Term("P", x), Term("Q", x))
            >>> theory.add(sentence=s)
            >>> compiler = PrologCompiler()
            >>> print(compiler.compile(theory))
            %% Predicate Definitions
            % P(x: str)
            % Q(x: str)
            <BLANKLINE>
            %% Sentences
            <BLANKLINE>
            q(X) :- p(X).

        There are multiple variants of Prolog syntax, the `PrologConfig` object can be used to control the output.
        Config arguments can be passed as kwargs to the `compile` method.

        :param theory: A Theory object to be compiled into prolog code
        :param syntax:
        :param kwargs: PrologConfig arguments
        :return:

        """
        config = self.config
        if self.config is None:
            config = PrologConfig(**kwargs)
        lines = []
        lines.append("%% Predicate Definitions")
        for pd in theory.predicate_definitions:
            args = ", ".join([f"{k}: {v}" for k, v in pd.arguments.items()])
            lines.append(f"% {pd.predicate}({args})")
        for sg in theory.sentence_groups:
            lines.append(f"\n%% {sg.name}\n")
            for s in sg.sentences or []:
                try:
                    lines.append(as_prolog(s, config, translate=True))
                except NotInProfileError as e:
                    self._add_untranslatable(s)
                    fol = as_fol(s)
                    fol = fol.replace("\n", " ")
                    lines.append(f"%% UNTRANSLATABLE: {fol}")
                    if self.strict:
                        raise e
        return "\n".join(lines)
