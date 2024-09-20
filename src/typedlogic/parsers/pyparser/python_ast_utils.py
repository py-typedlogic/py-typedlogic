import ast
import logging
import operator
from typing import Any, Callable, List, Mapping, Tuple, Union

from typedlogic import Implies, NegationAsFailure, Variable
from typedlogic.datamodel import (
    And,
    Exists,
    Forall,
    Iff,
    Implied,
    Not,
    Or,
    Sentence,
    SentenceGroup,
    Term,
)

logger = logging.getLogger(__name__)

AST_OP_TO_FUN: Mapping[str, Callable] = {
    'Add': operator.add,
    'Sub': operator.sub,
    'Mult': operator.mul,
    'Div': operator.truediv,
    'FloorDiv': operator.floordiv,
    'Mod': operator.mod,
    'Pow': operator.pow,
    'LShift': operator.lshift,
    'RShift': operator.rshift,
    'BitOr': operator.or_,
    'BitXor': operator.xor,
    'BitAnd': operator.and_,
    'MatMult': operator.matmul,
    # Comparison operators
    'Eq': operator.eq,
    'NotEq': operator.ne,
    'Lt': operator.lt,
    'LtE': operator.le,
    'Gt': operator.gt,
    'GtE': operator.ge,
    'Is': operator.is_,
    'IsNot': operator.is_not,
    'In': lambda x, y: x in y,
    'NotIn': lambda x, y: x not in y,
}



def parse_sentence(node: Union[ast.AST, List[ast.stmt]]) -> Sentence:
    """
    Parse an AST node into a Term instance.

        >>> tree = ast.parse("~(Person(name=x))")
        >>> func_def = tree.body[0]
        >>> sentence = parse_sentence(func_def)
        >>> assert isinstance(sentence, Not)
        >>> negated = sentence.operands[0]
        >>> assert isinstance(negated, Term)
        >>> negated
        Person(?x)

    :param node: The AST node to parse
    :type node: Union[ast.AST, List[ast.stmt]]
    :return: A Term instance
    """
    def tr_arg_or_kw_value(v: ast.expr) -> Any:
        if isinstance(v, ast.Constant):
            return v.value
        elif isinstance(v, ast.Name):
            return Variable(v.id)
        elif isinstance(v, (ast.BinOp, ast.UnaryOp, ast.Call)):
            return parse_sentence(v)
        else:
            raise ValueError(f"Unsupported argument type: {type(v)}")

    def parse_sentence_or_variable(v: ast.expr) -> Union[Sentence, Variable, Any]:
        if isinstance(v, ast.Name):
            return Variable(v.id)
        elif isinstance(v, ast.Constant):
            return v.value
        else:
            return parse_sentence(v)

    if isinstance(node, list):
        sentences = [parse_sentence(n) for n in node]
        if len(sentences) == 1:
            return sentences[0]
        else:
            return And(sentences)
    if isinstance(node, ast.Expr):
        return parse_sentence(node.value)
    if isinstance(node, ast.Assert):
        return parse_sentence(node.test)
    if isinstance(node, ast.BinOp):
        left = parse_sentence_or_variable(node.left)
        right = parse_sentence_or_variable(node.right)
        if isinstance(node.op, ast.RShift):
            assert isinstance(left, Sentence)
            assert isinstance(right, Sentence)
            return left >> right
        elif isinstance(node.op, ast.BitAnd):
            assert isinstance(left, Sentence)
            assert isinstance(right, Sentence)
            return left & right
        elif isinstance(node.op, ast.BitOr):
            assert isinstance(left, Sentence)
            assert isinstance(right, Sentence)
            return left | right
        elif isinstance(node.op, ast.BitXor):
            assert isinstance(left, Sentence)
            assert isinstance(right, Sentence)
            return left ^ right
        else:
            return Term(AST_OP_TO_FUN[node.op.__class__.__name__].__name__, left, right)
    elif isinstance(node, ast.BoolOp):
        operands = [parse_sentence(value) for value in node.values]
        if isinstance(node.op, ast.And):
            return And(*operands)
        elif isinstance(node.op, ast.Or):
            return Or(*operands)
        else:
            raise ValueError(f"Unsupported boolean operator: {type(node.op)}")
    elif isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.Invert):
            return ~parse_sentence(node.operand)
        elif isinstance(node.op, ast.Not):
            return Not(parse_sentence(node.operand))
        elif isinstance(node.op, ast.USub):
            return NegationAsFailure(parse_sentence(node.operand))
        else:
            raise ValueError(f"Unsupported unary operator: {type(node.op)}")
    elif isinstance(node, ast.If):
        # if COND: BODY
        test = node.test
        body = node.body
        orelse = node.orelse
        if orelse:
            raise ValueError("Else clause is not supported")
        return parse_sentence(test) >> parse_sentence(body)
    elif isinstance(node, ast.Call) and (isinstance(node.func, ast.Name) and node.func.id in ["Implies", "Iff", "Implied"]):
        if len(node.args) != 2:
            raise ValueError(f"Unsupported number of arguments for {node.func.id}: {len(node.args)}")
        left = parse_sentence(node.args[0])
        right = parse_sentence(node.args[1])
        if node.func.id == "Implies":
            return Implies(left, right)
        elif node.func.id == "Iff":
            return Iff(left, right)
        elif node.func.id == "Implied":
            return Implied(left, right)
        else:
            raise AssertionError
    elif isinstance(node, ast.Call):
        predicate = get_func_name(node.func)
        if predicate in ["all", "any"]:
            if len(node.args) != 1:
                raise ValueError(f"Unsupported number of arguments for quantifier: {len(node.args)}")
            arg0 = node.args[0]
            if not isinstance(arg0, ast.GeneratorExp):
                raise ValueError(f"Unsupported argument type for quantifier: {type(arg0)}")
            args, sentence = parse_generator_node(arg0)
            if predicate == "all":
                return Forall(args, sentence)
            else:
                return Exists(args, sentence)

        def tr_keyword(kw: ast.keyword) -> Tuple[str, Any]:
            if kw.arg is None:
                raise ValueError("Positional arguments are not supported")
            if isinstance(kw.value, ast.Constant):
                v = kw.value.value
            elif isinstance(kw.value, ast.Name):
                v = Variable(kw.value.id)
            elif isinstance(kw.value, (ast.BinOp, ast.UnaryOp, ast.Call)):
                kw_val_ast = kw.value
                if not isinstance(kw_val_ast, ast.AST):
                    raise AssertionError
                v = parse_sentence(kw_val_ast)
            else:
                raise ValueError(f"Unsupported keyword value type: {type(kw.value)}")
            return kw.arg, v
        if node.keywords:
            # keyword-based arguments are translated to a dict
            bindings = dict([tr_keyword(kw) for kw in node.keywords])
            return Term(predicate, bindings)
        elif node.args:
            # positional arguments are translated to a list
            pos_args = [tr_arg_or_kw_value(arg) for arg in node.args]
            return Term(predicate, *pos_args)
        else:
            return Term(predicate, {})
    elif isinstance(node, ast.Compare):
        left = tr_arg_or_kw_value(node.left)
        if len(node.comparators) != 1:
            raise ValueError(f"Unsupported number of comparators: {len(node.comparators)}")
        right = tr_arg_or_kw_value(node.comparators[0])
        if len(node.ops) != 1:
            raise ValueError(f"Unsupported number of operators: {len(node.ops)}")
        op = node.ops[0]
        op_name = AST_OP_TO_FUN[op.__class__.__name__].__name__
        return Term(op_name, left, right)
    elif isinstance(node, ast.GeneratorExp):
        raise ValueError("Generator expressions are not supported outside all/only")
    else:
        raise NotImplementedError(f"Unsupported node type: {type(node)}")


def parse_generator_node(node: ast.GeneratorExp) -> Tuple[List[Variable], Sentence]:
    """
    Parse a generator expression node and return the arguments and the implied sentence.

    :param node:
    :return:
    """
    elt = node.elt
    gens = node.generators
    if len(gens) != 1:
        raise ValueError(f"Unsupported number of generators: {len(gens)}")
    gen = gens[0]
    iter_node = gen.iter
    if isinstance(iter_node, ast.Call):
        iter_func, iter_args = parse_gen_call(iter_node)
    else:
        # iter_func = ast.unparse(iter_node)
        iter_args = []
    if gen.ifs:
        if_exprs = [parse_sentence(if_node) for if_node in gen.ifs]
        if_conj = if_exprs[0]
        for if_expr in if_exprs[1:]:
            if_conj &= if_expr
    else:
        if_conj = None

    # arg_types = {}
    if isinstance(gen.target, ast.Name):
        arg_types = {gen.target.id: Variable(gen.target.id, iter_args[0])}
    elif isinstance(gen.target, ast.Tuple):
        arg_types = {}
        for i, xelt in enumerate(gen.target.elts):
            if not isinstance(xelt, ast.Name):
                raise ValueError(f"Unsupported target type: {type(elt)}")
            arg_types[xelt.id] = Variable(xelt.id, iter_args[i])
    else:
        raise ValueError(f"Unsupported target type: {type(gen.target)}")

    implied_expr = parse_sentence(elt)
    impl: Sentence
    if if_conj:
        impl = Implies(if_conj, implied_expr)
    else:
        impl = implied_expr
    return list(arg_types.values()), impl


def get_func_name(node: ast.expr) -> str:
    """
    Recursively get the function name from an AST node.
    """
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return f"{get_func_name(node.value)}.{node.attr}"
    else:
        return ast.unparse(node)

def parse_gen_call(node: ast.Call) -> tuple[str, List[str]]:
    """
    Parse a gen() call node and return the function name and its arguments.
    """
    func_name = node.func.id if isinstance(node.func, ast.Name) else str(node.func)
    args = [ast.unparse(arg) for arg in node.args]
    return func_name, args


def parse_func(node: ast.Call) -> tuple[str, List[str]]:
    """
    Parse a gen() call node and return the function name and its arguments.
    """
    func_name = node.func.id if isinstance(node.func, ast.Name) else str(node.func)
    args = [ast.unparse(arg) for arg in node.args]
    return func_name, args


def parse_function_def_to_sentence_group(func_def: ast.FunctionDef) -> SentenceGroup:
    """
    Parse the AST of an axiom function and extract relevant information.

    :param func_def: The AST node of the axiom function
    :type func_def: ast.FunctionDef
    :return: A dataclass containing parsed information about the axiom
    :rtype: SentenceGroup

    :Example:

        >>> import ast
        >>> axiom_func = '''
        ... def all_persons_are_mortal_axiom() -> bool:
        ...     return all(
        ...         Person(name=x) >> Mortal(name=x)
        ...         for x in gen(NameType)
        ...     )
        ... '''
        >>> tree = ast.parse(axiom_func)
        >>> func_def = tree.body[0]  # Assuming the function is at the top level
        >>> sg = parse_function_def_to_sentence_group(func_def)
        >>> print(sg.name)
        all_persons_are_mortal_axiom
        >>> assert len(sg.sentences) == 1
        >>> sentence = sg.sentences[0]
        >>> assert isinstance(sentence, Forall)
        >>> print(sentence.quantifier)
        all
        >>> print(sentence.variables[0].name)
        x
        >>> print(sentence.variables[0].domain)
        NameType
        >>> imp = sentence.sentence
        >>> print(imp)
        (Person(?x) -> Mortal(?x))
        >>> assert isinstance(imp, Implies)
        >>> imp.operands[0]
        Person(?x)
        >>> imp.operands[0].predicate
        'Person'
        >>> imp.operands[0].bindings['name'].name
        'x'
    """
    sentence_collection = SentenceGroup(
        name=func_def.name,
        docstring=ast.get_docstring(func_def),
    )
    if not func_def.body:
        raise ValueError(f"No body found for axiom function: {func_def.name}")

    qvars = {}
    if func_def.args:
        args = func_def.args.args
        for arg in args:
            var_name = arg.arg
            if not arg.annotation:
                raise ValueError(f"Argument {var_name} is missing an annotation")
            arg_ann = arg.annotation
            if not isinstance(arg_ann, ast.Name):
                raise ValueError(f"Unsupported annotation type: {type(arg_ann)}")
            qvars[var_name] = Variable(var_name, arg_ann.id)

    sentences = []
    for body_node in func_def.body:
        def add_sentence(s: Sentence):
            if qvars:
                s = Forall([v for v in qvars.values()], s)
            sentences.append(s)
        if isinstance(body_node, ast.Return):
            if body_node.value:
                sentence = parse_sentence(body_node.value)
                add_sentence(sentence)
        elif isinstance(body_node, ast.Assert):
            sentence = parse_sentence(body_node.test)
            add_sentence(sentence)
        else:
            if isinstance(body_node, ast.If):
                sentence = parse_sentence(body_node)
                add_sentence(sentence)
            else:
                logger.info(f"Unsupported body type: {type(body_node)}")

    sentence_collection.sentences = sentences
    return sentence_collection


if __name__ == "__main__":
    import doctest

    doctest.testmod()
