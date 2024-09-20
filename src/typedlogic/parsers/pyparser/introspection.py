import ast
import importlib
import inspect
import types
import typing
from dataclasses import fields
from types import ModuleType
from typing import Any, Dict, List, NewType, Tuple, Type, Union

from typedlogic import Fact, FactMixin, Theory
from typedlogic.datamodel import DefinedType, PredicateDefinition, SentenceGroupType
from typedlogic.parsers.pyparser.python_ast_utils import SentenceGroup, parse_function_def_to_sentence_group
from typedlogic.transformations import ensure_terms_positional, sentences_from_predicate_hierarchy


def translate_module_to_theory(module: ModuleType) -> Theory:
    """
    Translate a module to a Theory object.

        >>> import tests.theorems.mortals as mortals
        >>> theory = translate_module_to_theory(mortals)
        >>> theory.name
        'tests.theorems.mortals'

    :param module:
    :return:
    """
    sgs = get_module_sentence_groups(module)
    pds = get_module_predicate_definitions(module)
    constants, tds = get_module_constants_and_types(module)
    # get the python module name
    theory = Theory(
        name=module.__name__,
        constants=constants,
        type_definitions=tds,
        predicate_definitions=list(pds.values()),
        sentence_groups=sgs,
    )
    ensure_terms_positional(theory)
    new_sentences = sentences_from_predicate_hierarchy(theory)
    for s in new_sentences:
        theory.add(s)
    return theory

# TODO: unused function; decide if we want to allow axiom-level
def get_axioms_ast(cls: Type):
    class_def = ast.parse(ast.unparse(ast.parse(inspect.getsource(cls))))
    for node in ast.walk(class_def):
        if isinstance(node, ast.ClassDef) and node.name == cls.__name__:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == 'axioms':
                    return item
    return None


def get_module_sentence_groups(module: Union[ModuleType, str]) -> List[SentenceGroup]:
    """
    Get the AST nodes of all axiom functions in a module.

    :param module: The module to introspect
    :return: A list of AST FunctionDef nodes for axiom functions
    """
    if not isinstance(module, str):
        module = inspect.getsource(module)
    module_ast = ast.parse(module)
    # module_vars = {k: v for k, v in vars(module).items() if not k.startswith('__')}
    sgs = []
    decorator_types = {x.value: x for x in SentenceGroupType}
    for node in module_ast.body:
        if isinstance(node, ast.FunctionDef):
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Name) and decorator.id in decorator_types:
                    sg = parse_function_def_to_sentence_group(node)
                    sg.group_type = decorator_types[decorator.id]
                    # TODO:
                    #if sg.argument_types is not None:
                    #    sg.argument_types = {k: safe_eval_type(v, module_vars) for k, v in sg.argument_types.items()}
                    sgs.append(sg)
                    break
    return sgs


def get_module_predicate_classes(module:  ModuleType) -> Dict[str, Type]:
    """
    Get all classes defined in a module.

    :param module: The module to introspect
    :return: A dictionary of class names to class types
    """
    module_vars = {k: v for k, v in vars(module).items() if not k.startswith('__')}
    classes = {}
    for name, obj in module_vars.items():
        if not inspect.isclass(obj):
            continue
        if inspect.isabstract(obj):
            continue
        if obj in {Fact, FactMixin}:
            continue
        if not issubclass(obj, FactMixin):
            continue
        classes[name] = obj
    return classes

JSON_SCHEMA_TYPE_MAP = {
    "string": "str",
    "number": "float",
    "integer": "int",
}

def introspect_attributes(cls: Type) -> dict[str, Any]:
    # https://stackoverflow.com/questions/69090253/how-to-iterate-over-attributes-of-dataclass-in-python
    try:

        import pydantic
        if issubclass(cls, pydantic.BaseModel):
            schema = cls.model_json_schema()
            r = {}
            for p, p_schema in schema['properties'].items():
                def _parse_type(s) -> DefinedType:
                    if 'anyOf' in s:
                        return [_parse_type(x) for x in s['anyOf']]
                    return s.get('type', 'str')
                t = _parse_type(p_schema)
                if isinstance(t, str):
                    r[p] = JSON_SCHEMA_TYPE_MAP.get(t, t)
                else:
                    # TODO
                    r[p] = JSON_SCHEMA_TYPE_MAP['string']
            return r
    except ImportError:
        pass    # Get all attributes of the class
    if fields(cls):
        r = {field.name: field.type.__name__ for field in fields(cls)}
        return r

    attributes = inspect.getmembers(cls)

    # Filter out class variables and built-in attributes
    non_classvar_attributes = [
        attr for attr in attributes
        if not isinstance(attr[1], type)
           and not attr[0].startswith('__')
           and not attr[0].startswith('_')
           and not inspect.ismethod(attr[1])
           and not inspect.isfunction(attr[1])
    ]

    return {attr[0]: attr[1] for attr in non_classvar_attributes}

def get_module_constants(module: ModuleType) -> Dict[str, Any]:
    """
    Get all constants defined in a module.

    :param module: The module to introspect
    :return: A dictionary of constant names to constant values
    """
    module_vars = {k: v for k, v in vars(module).items() if not k.startswith('__')}
    constants = {}
    for name, obj in module_vars.items():
        if not inspect.isclass(obj) and not inspect.isfunction(obj):
            constants[name] = obj
    return constants


def is_union(t):
    if str(t).startswith('typing.Union'):
        return True
    # For Python 3.10+
    if hasattr(types, "UnionType"):
        return isinstance(t, types.UnionType)

    # For earlier versions
    return typing.get_origin(t) is Union

def get_module_constants_and_types(module: ModuleType) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    module_vars = {k: v for k, v in vars(module).items() if not k.startswith('__')}
    constants = {}
    types: Dict[str, DefinedType] = {}
    for name, obj in module_vars.items():
        if not inspect.isfunction(obj):
            if inspect.isclass(obj):
                t = obj.__name__
                if t != name:
                    types[name] = t
            elif is_union(obj):
                t = obj.__name__
                if t != name:
                    types[name] = [x.__name__ for x in typing.get_args(obj)]
            elif isinstance(obj, NewType):
                st = obj.__supertype__
                if isinstance(st, type):
                    types[name] = st.__name__
                else:
                    types[name] = str(st)
            else:
                constants[name] = obj
    return constants, types

def get_module_predicate_definitions(module: ModuleType) -> Dict[str, PredicateDefinition]:
    """
    Get all predicate classes defined in a module.

    Assume a module with the following (Pydantic) class:

        >>> from pydantic import BaseModel
        >>> from typedlogic import FactMixin
        >>> class PersonWithAge(BaseModel, FactMixin):
        ...   name: str
        ...   age: int

    This is in one of the tests:

        >>> import tests.theorems.types_example as types_example
        >>> pds = get_module_predicate_definitions(types_example)
        >>> list(pds.keys())
        ['PersonWithAge', 'Adult', 'StageAge']
        >>> pd = pds['PersonWithAge']
        >>> pd.predicate
        'PersonWithAge'
        >>> pd.arguments
        {'name': 'str', 'age': 'int'}

    :param module:
    :return:
    """
    cls_name_map = get_module_predicate_classes(module)
    pds = {}
    parent_map = {}
    cls_to_pd = {}
    for name, cls in cls_name_map.items():
        pd = PredicateDefinition(name, introspect_attributes(cls))
        pds[name] = pd
        # get python parent classes
        parent_map[pd.predicate] = cls.__bases__
        cls_to_pd[cls] = pd
    for predicate, pd in pds.items():
        pd.parents = []
        for parent in parent_map[predicate]:
            if parent in cls_to_pd:
                pd.parents.append(cls_to_pd[parent].predicate)

    return pds


def safe_eval_type(type_str: str, globals_dict: Dict[str, Any]) -> Any:
    """
    Safely evaluate a type string, considering potential imports.

    :param type_str: The string representation of the type to evaluate
    :type type_str: str
    :param globals_dict: A dictionary of global variables, including imports
    :type globals_dict: Dict[str, Any]
    :return: The evaluated type
    :rtype: Any

    :raises ValueError: If the type cannot be evaluated safely
    """
    try:
        # First, try to evaluate as is (handles built-in types and already imported types)
        return eval(type_str, globals_dict)
    except NameError:
        # If NameError, it might be due to an import. Let's try to import it.
        module_parts = type_str.split('.')
        for i in range(1, len(module_parts)):
            try:
                module_name = '.'.join(module_parts[:i])
                globals_dict[module_parts[0]] = importlib.import_module(module_name)
                return eval(type_str, globals_dict)
            except ImportError:
                continue
        raise ValueError(f"Cannot safely evaluate type: {type_str}")
