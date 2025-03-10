import tempfile
from typing import Optional, Union, ClassVar

from typedlogic import Theory
from typedlogic.compiler import Compiler, ModelSyntax
from typedlogic.integrations.frameworks.hornedowl.horned_owl_bridge import theory_to_py_indexed_ontology


class OWLCompiler(Compiler):
    """
    Writes theories to OWL files.

    TODO: this is incomplete

    Uses py-horned-owl

    Example:
    -------
        >>> from typedlogic.integrations.frameworks.owldl import OWLPyParser
        >>> from typedlogic.transformations import as_fol
        >>> import tests.test_frameworks.owldl.family as family
        >>> parser = OWLPyParser()
        >>> #theory = parser.parse_file(family.__file__)
        >>> #compiler = OWLCompiler()
        >>> #print(compiler.compile(theory))


    """

    default_suffix: ClassVar[str] = "owl"

    def compile(self, theory: Theory, syntax: Optional[Union[str, ModelSyntax]] = None, **kwargs) -> str:
        pho_ontology = theory_to_py_indexed_ontology(theory)
        with tempfile.NamedTemporaryFile(suffix=".owl", mode="w") as fp:
            pho_ontology.save_to_file(fp.name, str(syntax) if syntax else "ofn")
            fp.flush()
            with open(fp.name) as f_read:
                return f_read.read()
