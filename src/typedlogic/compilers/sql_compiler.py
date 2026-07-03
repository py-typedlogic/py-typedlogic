"""
SQL compilation for TypedLogic theories and goals.

The compiler treats extensional predicates as tables or inline facts and treats
Horn-rule predicates as SQL common table expressions. Non-recursive rules become
ordinary CTEs; self-recursive rules use ``WITH RECURSIVE`` when enabled.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, ClassVar, Iterable, Mapping, Optional, Sequence, Union

from typedlogic.compiler import Compiler, ModelSyntax
from typedlogic.datamodel import (
    And,
    Exists,
    Extension,
    Forall,
    Implies,
    NegationAsFailure,
    Not,
    NotInProfileError,
    Or,
    PredicateDefinition,
    Sentence,
    Term,
    Theory,
    Variable,
)
from typedlogic.transformations import conjunction_as_list, to_horn_rules

SQL_INFIX_OPERATORS: Mapping[str, str] = {
    "eq": "=",
    "ne": "<>",
    "lt": "<",
    "le": "<=",
    "gt": ">",
    "ge": ">=",
    "add": "+",
    "sub": "-",
    "mul": "*",
    "truediv": "/",
    "mod": "%",
}

BindingSpec = Union["PredicateBinding", str, Mapping[str, Any]]


class SQLTranslationError(NotInProfileError):
    """Raised when a sentence cannot be represented in portable SQL."""


@dataclass(frozen=True)
class PredicateBinding:
    """
    Binding from a logical predicate to an existing SQL table or view.

    ``columns`` may be a sequence in predicate argument order or a mapping from
    logical argument names to physical SQL column names.
    """

    table: str
    columns: Optional[Union[Sequence[str], Mapping[str, str]]] = None
    schema: Optional[str] = None


@dataclass
class SQLCompilerConfig:
    """Options controlling SQL generation."""

    bindings: Mapping[str, PredicateBinding] = field(default_factory=dict)
    quote_identifiers: bool = False
    use_recursive_cte: bool = True
    union_all: bool = False
    include_ground_facts: bool = True
    query_limit: Optional[int] = None


@dataclass(frozen=True)
class RelationSpec:
    """Logical and physical metadata for one predicate relation."""

    predicate: str
    columns: tuple[str, ...]
    binding: Optional[PredicateBinding] = None


@dataclass
class BodySQL:
    """SQL fragments produced from a conjunction or goal."""

    from_items: list[str] = field(default_factory=list)
    where: list[str] = field(default_factory=list)
    variables: dict[str, str] = field(default_factory=dict)


@dataclass
class RulePlan:
    """A Horn rule grouped by the predicate in its head."""

    rule: Implies
    dependencies: tuple[str, ...]


@dataclass
class SQLBuildContext:
    """Shared state for one SQL compilation."""

    theory: Theory
    config: SQLCompilerConfig
    relations: dict[str, RelationSpec]
    cte_predicates: set[str]
    cte_order: list[str]

    def ident(self, name: str) -> str:
        """Return a SQL identifier."""
        return quote_identifier(name, quote=self.config.quote_identifiers)

    def table_ref(self, binding: PredicateBinding) -> str:
        """Return a possibly schema-qualified table reference."""
        table = self.ident(binding.table)
        if binding.schema:
            return f"{self.ident(binding.schema)}.{table}"
        return table


def quote_identifier(name: str, quote: bool = False) -> str:
    """Quote a SQL identifier when requested or required."""
    if not name:
        raise SQLTranslationError("SQL identifiers cannot be empty")
    if not quote and name.replace("_", "").isalnum() and not name[0].isdigit():
        return name
    return '"' + name.replace('"', '""') + '"'


def sql_literal(value: Any) -> str:
    """Render a Python literal as a SQL literal."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if hasattr(value, "isoformat"):
        value = value.isoformat()
    return "'" + str(value).replace("'", "''") + "'"


def normalize_bindings(bindings: Optional[Mapping[str, BindingSpec]]) -> dict[str, PredicateBinding]:
    """Normalize user-friendly binding specifications."""
    normalized: dict[str, PredicateBinding] = {}
    for predicate, binding in (bindings or {}).items():
        normalized[predicate] = normalize_binding(binding)
    return normalized


def normalize_binding(binding: BindingSpec) -> PredicateBinding:
    """Convert a binding specification to a ``PredicateBinding``."""
    if isinstance(binding, PredicateBinding):
        return binding
    if isinstance(binding, str):
        return PredicateBinding(table=binding)
    table = binding.get("table")
    if not isinstance(table, str):
        raise SQLTranslationError(f"Binding mapping must include a string 'table': {binding}")
    columns = binding.get("columns")
    schema = binding.get("schema")
    if schema is not None and not isinstance(schema, str):
        raise SQLTranslationError(f"Binding schema must be a string: {binding}")
    return PredicateBinding(table=table, columns=columns, schema=schema)


def term_predicates(sentence: Sentence) -> list[str]:
    """Return relation predicates mentioned in a sentence."""
    predicates: list[str] = []
    for term in terms_in_sentence(sentence):
        if term.predicate not in SQL_INFIX_OPERATORS:
            predicates.append(term.predicate)
    return predicates


def terms_in_sentence(sentence: Sentence) -> list[Term]:
    """Return all terms occurring in a sentence."""
    if isinstance(sentence, Extension):
        return terms_in_sentence(sentence.to_model_object())
    if isinstance(sentence, Term):
        terms = [sentence]
        for value in sentence.values:
            if isinstance(value, Sentence):
                terms.extend(terms_in_sentence(value))
        return terms
    if isinstance(sentence, (And, Or)):
        return [term for operand in sentence.operands for term in terms_in_sentence(operand)]
    if isinstance(sentence, (Not, NegationAsFailure)):
        return terms_in_sentence(sentence.negated)
    if isinstance(sentence, Forall):
        return terms_in_sentence(sentence.sentence)
    if isinstance(sentence, Exists):
        return terms_in_sentence(sentence.sentence)
    if isinstance(sentence, Implies):
        return terms_in_sentence(sentence.antecedent) + terms_in_sentence(sentence.consequent)
    return []


def free_variables(sentence: Sentence) -> list[Variable]:
    """Return free variables in first-use order."""
    seen: set[str] = set()
    variables: list[Variable] = []
    for variable in _free_variables(sentence, bound=set()):
        if variable.name not in seen:
            seen.add(variable.name)
            variables.append(variable)
    return variables


def _free_variables(sentence: Sentence, bound: set[str]) -> list[Variable]:
    if isinstance(sentence, Extension):
        return _free_variables(sentence.to_model_object(), bound)
    if isinstance(sentence, Term):
        return _free_variables_in_term(sentence, bound)
    if isinstance(sentence, (And, Or)):
        return [var for operand in sentence.operands for var in _free_variables(operand, bound)]
    if isinstance(sentence, (Not, NegationAsFailure)):
        return _free_variables(sentence.negated, bound)
    if isinstance(sentence, Exists):
        return _free_variables(sentence.sentence, bound | {var.name for var in sentence.variables})
    if isinstance(sentence, Forall):
        return _free_variables(sentence.sentence, bound | {var.name for var in sentence.variables})
    if isinstance(sentence, Implies):
        return _free_variables(sentence.antecedent, bound) + _free_variables(sentence.consequent, bound)
    return []


def _free_variables_in_term(term: Term, bound: set[str]) -> list[Variable]:
    variables: list[Variable] = []
    for value in term.values:
        if isinstance(value, Variable) and value.name not in bound:
            variables.append(value)
        if isinstance(value, Sentence):
            variables.extend(_free_variables(value, bound))
    return variables


@dataclass
class SQLCompiler(Compiler):
    """Compiler that translates TypedLogic rules plus a goal/query to SQL."""

    default_suffix: ClassVar[str] = "sql"
    config: Optional[SQLCompilerConfig] = None

    def compile(self, theory: Theory, syntax: Optional[Union[str, ModelSyntax]] = None, **kwargs: Any) -> str:
        """
        Compile a theory and optional goal into SQL.

        :param theory: logical theory to translate
        :param syntax: ignored; present for the compiler interface
        :param kwargs: ``goal``, ``bindings``, or any ``SQLCompilerConfig`` field
        :return: SQL text
        """
        goal = kwargs.pop("goal", None)
        config = self._resolve_config(kwargs)
        if goal is not None:
            return self.compile_query(theory, goal, config=config)
        if theory.goals:
            return "\n\n".join(
                self.compile_query(theory, goal_sentence, config=config) + ";" for goal_sentence in theory.goals
            )
        return self.compile_relations(theory, config=config)

    def compile_query(
        self,
        theory: Theory,
        goal: Sentence,
        config: Optional[SQLCompilerConfig] = None,
    ) -> str:
        """Compile a goal/query against a theory to a SQL ``SELECT`` statement."""
        resolved = config or self.config or SQLCompilerConfig()
        horn_rules = horn_rules_for(theory)
        context = build_context(theory, resolved, horn_rules, extra_sentences=[goal])
        ctes = compile_ctes(horn_rules, context)
        query = compile_goal_select(goal, context)
        return attach_with_clause(query, ctes, recursive=uses_recursive_cte(horn_rules, context))

    def compile_constraints(
        self,
        theory: Theory,
        config: Optional[SQLCompilerConfig] = None,
    ) -> list[str]:
        """Compile FOL denial constraints to SQL queries that return violating rows."""
        resolved = config or self.config or SQLCompilerConfig()
        horn_rules = horn_rules_for(theory)
        context = build_context(theory, resolved, horn_rules)
        ctes = compile_ctes(horn_rules, context)
        constraints = [rule for rule in horn_rules if is_constraint_rule(rule)]
        return [
            attach_with_clause(
                compile_constraint_select(rule, context, index), ctes, uses_recursive_cte(horn_rules, context)
            )
            for index, rule in enumerate(constraints, start=1)
        ]

    def compile_relations(
        self,
        theory: Theory,
        config: Optional[SQLCompilerConfig] = None,
    ) -> str:
        """Compile each derived relation into a standalone inspection query."""
        resolved = config or self.config or SQLCompilerConfig()
        horn_rules = horn_rules_for(theory)
        context = build_context(theory, resolved, horn_rules)
        ctes = compile_ctes(horn_rules, context)
        recursive = uses_recursive_cte(horn_rules, context)
        queries = []
        for predicate in context.cte_order:
            select = f"SELECT * FROM {context.ident(predicate)}"  # noqa: S608
            queries.append(attach_with_clause(select, ctes, recursive=recursive) + ";")
        return "\n\n".join(queries)

    def _resolve_config(self, kwargs: Mapping[str, Any]) -> SQLCompilerConfig:
        config = replace(self.config) if self.config else SQLCompilerConfig()
        options = dict(kwargs)
        if "bindings" in options:
            config.bindings = normalize_bindings(options.pop("bindings"))
        for key, value in options.items():
            if not hasattr(config, key):
                raise TypeError(f"Unknown SQL compiler option: {key}")
            setattr(config, key, value)
        return config


def horn_rules_for(theory: Theory) -> list[Implies]:
    """Convert all theory sentences to Horn-style SQL rule candidates."""
    rules: list[Implies] = []
    sentences = [
        sentence
        for group in theory.asserted_sentence_groups
        for sentence in group.sentences or []
    ]
    for sentence in sentences:
        for rule in to_horn_rules(sentence, allow_goal_clauses=True):
            if isinstance(rule, Implies):
                rules.append(rule)
            elif isinstance(rule, Or) and not rule.operands:
                rules.append(Implies(And(), Or()))
            else:
                raise SQLTranslationError(f"Cannot translate non-implication Horn clause to SQL: {rule}")
    return rules


def build_context(
    theory: Theory,
    config: SQLCompilerConfig,
    horn_rules: Sequence[Implies],
    extra_sentences: Optional[Iterable[Sentence]] = None,
) -> SQLBuildContext:
    """Build relation metadata and CTE ordering."""
    relations = build_relation_specs(theory, config, horn_rules, extra_sentences=extra_sentences)
    cte_predicates = predicates_requiring_ctes(horn_rules, config)
    cte_order = topological_cte_order(horn_rules, cte_predicates)
    return SQLBuildContext(
        theory=theory, config=config, relations=relations, cte_predicates=cte_predicates, cte_order=cte_order
    )


def build_relation_specs(
    theory: Theory,
    config: SQLCompilerConfig,
    horn_rules: Sequence[Implies],
    extra_sentences: Optional[Iterable[Sentence]] = None,
) -> dict[str, RelationSpec]:
    """Build relation specs from predicate definitions, rules, bindings, and goals."""
    predicate_definitions = {pd.predicate: pd for pd in theory.predicate_definitions}
    samples = collect_sample_terms(theory, horn_rules, extra_sentences=extra_sentences)
    predicates = set(samples) | set(predicate_definitions) | set(config.bindings)
    return {
        predicate: RelationSpec(
            predicate=predicate,
            columns=columns_for_predicate(
                predicate, predicate_definitions.get(predicate), config.bindings.get(predicate), samples
            ),
            binding=config.bindings.get(predicate),
        )
        for predicate in sorted(predicates)
    }


def collect_sample_terms(
    theory: Theory,
    horn_rules: Sequence[Implies],
    extra_sentences: Optional[Iterable[Sentence]] = None,
) -> dict[str, Term]:
    """Collect one representative term for each relation predicate."""
    samples: dict[str, Term] = {}
    sentences: list[Sentence] = list(theory.sentences) + list(horn_rules)
    if extra_sentences:
        sentences.extend(extra_sentences)
    for sentence in sentences:
        for term in terms_in_sentence(sentence):
            if term.predicate not in SQL_INFIX_OPERATORS and term.predicate not in samples:
                samples[term.predicate] = term
    return samples


def columns_for_predicate(
    predicate: str,
    predicate_definition: Optional[PredicateDefinition],
    binding: Optional[PredicateBinding],
    samples: Mapping[str, Term],
) -> tuple[str, ...]:
    """Infer logical column names for a predicate."""
    if predicate_definition:
        return tuple(predicate_definition.arguments)
    if binding and isinstance(binding.columns, Mapping):
        return tuple(binding.columns)
    sample = samples.get(predicate)
    if sample and sample.positional is False:
        return tuple(sample.bindings)
    if binding and isinstance(binding.columns, Sequence) and not isinstance(binding.columns, str):
        return tuple(str(column) for column in binding.columns)
    if sample:
        return tuple(f"arg{index}" for index, _ in enumerate(sample.values))
    return ()


def predicates_requiring_ctes(horn_rules: Sequence[Implies], config: SQLCompilerConfig) -> set[str]:
    """Return predicates that need CTE definitions."""
    predicates: set[str] = set()
    for rule in horn_rules:
        head = rule.consequent
        if isinstance(head, Term):
            if config.include_ground_facts or not is_ground_fact_rule(rule):
                predicates.add(head.predicate)
    return predicates


def topological_cte_order(horn_rules: Sequence[Implies], cte_predicates: set[str]) -> list[str]:
    """Order CTEs so dependencies are available before consumers."""
    dependencies = dependencies_by_head(horn_rules, cte_predicates)
    pending = set(cte_predicates)
    ordered: list[str] = []
    while pending:
        ready = [predicate for predicate in sorted(pending) if not (dependencies[predicate] - {predicate}) & pending]
        if not ready:
            cycle = ", ".join(sorted(pending))
            raise SQLTranslationError(f"Mutually recursive SQL CTEs are not supported: {cycle}")
        ordered.extend(ready)
        pending.difference_update(ready)
    return ordered


def dependencies_by_head(horn_rules: Sequence[Implies], cte_predicates: set[str]) -> dict[str, set[str]]:
    """Collect CTE dependencies for each head predicate."""
    dependencies: dict[str, set[str]] = {predicate: set() for predicate in cte_predicates}
    for rule in horn_rules:
        head = rule.consequent
        if isinstance(head, Term) and head.predicate in dependencies:
            dependencies[head.predicate].update(
                predicate for predicate in term_predicates(rule.antecedent) if predicate in cte_predicates
            )
    return dependencies


def compile_ctes(horn_rules: Sequence[Implies], context: SQLBuildContext) -> list[str]:
    """Compile all CTE definitions needed by the goal."""
    rules_by_head = group_rules_by_head(horn_rules)
    ctes: list[str] = []
    for predicate in context.cte_order:
        ctes.append(compile_relation_cte(predicate, rules_by_head.get(predicate, []), context))
    return ctes


def group_rules_by_head(horn_rules: Sequence[Implies]) -> dict[str, list[Implies]]:
    """Group rules by head predicate."""
    grouped: dict[str, list[Implies]] = {}
    for rule in horn_rules:
        if isinstance(rule.consequent, Term):
            grouped.setdefault(rule.consequent.predicate, []).append(rule)
    return grouped


def compile_relation_cte(predicate: str, rules: Sequence[Implies], context: SQLBuildContext) -> str:
    """Compile one relation CTE."""
    relation = context.relations[predicate]
    anchors, recursive = split_rule_selects(predicate, rules, context)
    if recursive and not context.config.use_recursive_cte:
        raise SQLTranslationError(f"Recursive relation {predicate} requires use_recursive_cte=True")
    if relation.binding:
        anchors.insert(0, compile_binding_select(relation, relation.binding, context))
    if not anchors and recursive:
        raise SQLTranslationError(f"Recursive relation {predicate} has no non-recursive anchor")
    branches = anchors + recursive
    if not branches:
        raise SQLTranslationError(f"Relation {predicate} has no SQL source")
    union = "UNION ALL" if context.config.union_all else "UNION"
    body = f"\n{indent(f' {union} '.join(branches))}\n"
    columns = ", ".join(context.ident(column) for column in relation.columns)
    return f"{context.ident(predicate)}({columns}) AS ({body})"


def split_rule_selects(
    predicate: str,
    rules: Sequence[Implies],
    context: SQLBuildContext,
) -> tuple[list[str], list[str]]:
    """Split a predicate's rule SELECTs into non-recursive and recursive branches."""
    anchors: list[str] = []
    recursive: list[str] = []
    for rule in rules:
        if is_ground_fact_rule(rule) and not context.config.include_ground_facts:
            continue
        select = compile_rule_select(rule, context)
        if predicate in term_predicates(rule.antecedent):
            recursive.append(select)
        else:
            anchors.append(select)
    return anchors, recursive


def compile_binding_select(relation: RelationSpec, binding: PredicateBinding, context: SQLBuildContext) -> str:
    """Compile an external table binding as a relation-shaped SELECT."""
    alias = "_base"
    select_items = []
    for column in relation.columns:
        physical = physical_column(relation, column)
        select_items.append(f"{alias}.{context.ident(physical)} AS {context.ident(column)}")
    return f"SELECT {', '.join(select_items)} FROM {context.table_ref(binding)} AS {alias}"  # noqa: S608


def compile_rule_select(rule: Implies, context: SQLBuildContext) -> str:
    """Compile one Horn rule to a SELECT branch."""
    if not isinstance(rule.consequent, Term):
        raise SQLTranslationError(f"Rule has no relation head: {rule}")
    head = rule.consequent
    relation = context.relations[head.predicate]
    body = compile_body(rule.antecedent, context, alias_prefix="_r")
    select_items = compile_head_select_items(head, relation, body, context)
    sql = f"SELECT {', '.join(select_items)}"
    if body.from_items:
        sql += f" FROM {', '.join(body.from_items)}"
    if body.where:
        sql += f" WHERE {' AND '.join(body.where)}"
    return sql


def compile_head_select_items(head: Term, relation: RelationSpec, body: BodySQL, context: SQLBuildContext) -> list[str]:
    """Compile SELECT expressions for a rule head."""
    bindings = term_argument_bindings(head, relation)
    select_items: list[str] = []
    for column, value in bindings:
        expression = value_expression(value, body, context)
        select_items.append(f"{expression} AS {context.ident(column)}")
    return select_items


def compile_body(sentence: Sentence, context: SQLBuildContext, alias_prefix: str) -> BodySQL:
    """Compile a supported body sentence to FROM and WHERE fragments."""
    if isinstance(sentence, Extension):
        sentence = sentence.to_model_object()
    if isinstance(sentence, Forall):
        sentence = sentence.sentence
    if isinstance(sentence, Exists):
        sentence = sentence.sentence
    body = BodySQL()
    operands = conjunction_as_list(sentence)
    positive, builtin, negative = partition_body_operands(operands)
    alias_counter = 0
    for term in positive:
        alias_counter = add_positive_term(term, body, context, alias_prefix, alias_counter)
    for term in builtin:
        add_builtin_condition(term, body, context)
    for negated in negative:
        alias_counter = add_negated_term(negated, body, context, alias_prefix, alias_counter)
    return body


def partition_body_operands(operands: Sequence[Sentence]) -> tuple[list[Term], list[Term], list[Term]]:
    """Partition body operands into relational, builtin, and negated terms."""
    positive: list[Term] = []
    builtin: list[Term] = []
    negative: list[Term] = []
    for operand in operands:
        if isinstance(operand, Term):
            if operand.predicate in SQL_INFIX_OPERATORS:
                builtin.append(operand)
            else:
                positive.append(operand)
        elif isinstance(operand, (Not, NegationAsFailure)) and isinstance(operand.negated, Term):
            negative.append(operand.negated)
        elif isinstance(operand, Or) and not operand.operands:
            continue
        elif isinstance(operand, And):
            nested_positive, nested_builtin, nested_negative = partition_body_operands(list(operand.operands))
            positive.extend(nested_positive)
            builtin.extend(nested_builtin)
            negative.extend(nested_negative)
        else:
            raise SQLTranslationError(f"Unsupported SQL body operand: {operand}")
    return positive, builtin, negative


def add_positive_term(
    term: Term,
    body: BodySQL,
    context: SQLBuildContext,
    alias_prefix: str,
    alias_counter: int,
) -> int:
    """Add a positive relational atom to the body SQL."""
    relation = context.relations[term.predicate]
    alias = f"{alias_prefix}{alias_counter}"
    alias_counter += 1
    body.from_items.append(f"{relation_from_sql(relation, context)} AS {alias}")
    add_term_conditions(term, relation, alias, body, context)
    return alias_counter


def add_negated_term(
    term: Term,
    body: BodySQL,
    context: SQLBuildContext,
    alias_prefix: str,
    alias_counter: int,
) -> int:
    """Add a negated relational atom as a correlated NOT EXISTS condition."""
    relation = context.relations[term.predicate]
    alias = f"{alias_prefix}{alias_counter}"
    alias_counter += 1
    nested = BodySQL()
    add_term_conditions(term, relation, alias, nested, context, outer=body)
    where = "" if not nested.where else " WHERE " + " AND ".join(nested.where)
    body.where.append(f"NOT EXISTS (SELECT 1 FROM {relation_from_sql(relation, context)} AS {alias}{where})")  # noqa: S608
    return alias_counter


def add_term_conditions(
    term: Term,
    relation: RelationSpec,
    alias: str,
    body: BodySQL,
    context: SQLBuildContext,
    outer: Optional[BodySQL] = None,
) -> None:
    """Add equality and constant filters for a relational atom."""
    for column, value in term_argument_bindings(term, relation):
        column_ref = f"{alias}.{context.ident(sql_column_name(relation, column, context))}"
        if isinstance(value, Variable):
            add_variable_binding(value.name, column_ref, body, outer=outer)
        else:
            body.where.append(f"{column_ref} {null_safe_equals(value)} {sql_literal(value)}")


def add_variable_binding(variable: str, column_ref: str, body: BodySQL, outer: Optional[BodySQL] = None) -> None:
    """Bind or constrain a variable reference."""
    if variable in body.variables:
        body.where.append(f"{body.variables[variable]} = {column_ref}")
    elif outer and variable in outer.variables:
        body.where.append(f"{column_ref} = {outer.variables[variable]}")
    else:
        body.variables[variable] = column_ref


def add_builtin_condition(term: Term, body: BodySQL, context: SQLBuildContext) -> None:
    """Add a builtin comparison or arithmetic condition."""
    values = list(term.values)
    if len(values) != 2:
        raise SQLTranslationError(f"SQL builtin {term.predicate} requires two arguments")
    left = value_expression(values[0], body, context)
    right = value_expression(values[1], body, context)
    operator = SQL_INFIX_OPERATORS[term.predicate]
    body.where.append(f"{left} {operator} {right}")


def value_expression(value: Any, body: BodySQL, context: SQLBuildContext) -> str:
    """Compile a term argument or builtin expression to SQL."""
    if isinstance(value, Variable):
        if value.name not in body.variables:
            raise SQLTranslationError(f"Variable {value.name} is not bound in SQL body")
        return body.variables[value.name]
    if isinstance(value, Term) and value.predicate in SQL_INFIX_OPERATORS:
        return builtin_expression(value, body, context)
    if isinstance(value, Term):
        raise SQLTranslationError(f"Nested relation terms are not supported in SQL expressions: {value}")
    return sql_literal(value)


def builtin_expression(term: Term, body: BodySQL, context: SQLBuildContext) -> str:
    """Compile an infix builtin expression."""
    values = list(term.values)
    if len(values) != 2:
        raise SQLTranslationError(f"SQL builtin {term.predicate} requires two arguments")
    left = value_expression(values[0], body, context)
    right = value_expression(values[1], body, context)
    return f"({left} {SQL_INFIX_OPERATORS[term.predicate]} {right})"


def compile_goal_select(goal: Sentence, context: SQLBuildContext) -> str:
    """Compile a goal into a SELECT statement."""
    goal = unwrap_query_quantifier(goal)
    body = compile_body(goal, context, alias_prefix="_q")
    variables = free_variables(goal)
    if variables:
        missing = [var.name for var in variables if var.name not in body.variables]
        if missing:
            joined = ", ".join(missing)
            raise SQLTranslationError(f"Free variable(s) are not bound by positive SQL atoms: {joined}")
        select_items = [f"{body.variables[var.name]} AS {context.ident(var.name)}" for var in variables]
        sql = f"SELECT DISTINCT {', '.join(select_items)}"
        sql = append_from_where_limit(sql, body, context)
        return sql
    inner = "SELECT 1"
    inner = append_from_where_limit(inner, body, context)
    return f"SELECT CASE WHEN EXISTS ({inner}) THEN 1 ELSE 0 END AS holds"


def compile_constraint_select(rule: Implies, context: SQLBuildContext, index: int) -> str:
    """Compile a denial constraint to a SELECT returning violation witnesses."""
    body = compile_body(rule.antecedent, context, alias_prefix=f"_c{index}_")
    variables = sorted(body.variables)
    if variables:
        select_items = [f"{body.variables[var]} AS {context.ident(var)}" for var in variables]
    else:
        select_items = [f"{index} AS constraint_id"]
    sql = f"SELECT DISTINCT {', '.join(select_items)}"
    return append_from_where_limit(sql, body, context)


def append_from_where_limit(sql: str, body: BodySQL, context: SQLBuildContext) -> str:
    """Append FROM, WHERE, and LIMIT clauses to a SELECT prefix."""
    if body.from_items:
        sql += f" FROM {', '.join(body.from_items)}"
    if body.where:
        sql += f" WHERE {' AND '.join(body.where)}"
    if context.config.query_limit is not None:
        sql += f" LIMIT {context.config.query_limit}"
    return sql


def unwrap_query_quantifier(goal: Sentence) -> Sentence:
    """Strip top-level quantifiers for SQL query generation."""
    if isinstance(goal, Extension):
        return unwrap_query_quantifier(goal.to_model_object())
    if isinstance(goal, (Forall, Exists)):
        return goal.sentence
    return goal


def attach_with_clause(query: str, ctes: Sequence[str], recursive: bool) -> str:
    """Attach a WITH clause to a query when CTEs exist."""
    if not ctes:
        return query
    keyword = "WITH RECURSIVE" if recursive else "WITH"
    joined_ctes = ",\n".join(ctes)
    return f"{keyword}\n{joined_ctes}\n{query}"


def uses_recursive_cte(horn_rules: Sequence[Implies], context: SQLBuildContext) -> bool:
    """Return whether generated SQL needs WITH RECURSIVE."""
    if not context.config.use_recursive_cte:
        return False
    for rule in horn_rules:
        if isinstance(rule.consequent, Term) and rule.consequent.predicate in term_predicates(rule.antecedent):
            return True
    return False


def is_constraint_rule(rule: Implies) -> bool:
    """Return whether a Horn rule is a denial constraint."""
    return isinstance(rule.consequent, Or) and not rule.consequent.operands


def is_ground_fact_rule(rule: Implies) -> bool:
    """Return whether a rule is a ground unit clause."""
    return isinstance(rule.antecedent, And) and not rule.antecedent.operands and isinstance(rule.consequent, Term)


def term_argument_bindings(term: Term, relation: RelationSpec) -> list[tuple[str, Any]]:
    """Pair a term's arguments with logical relation columns."""
    if term.positional is False:
        missing = [column for column in relation.columns if column not in term.bindings]
        extra = [column for column in term.bindings if column not in relation.columns]
        if missing or extra:
            raise SQLTranslationError(
                f"Predicate {term.predicate} has mismatched keyword arguments; missing={missing}, extra={extra}"
            )
        return [(column, term.bindings[column]) for column in relation.columns]
    if len(term.values) != len(relation.columns):
        raise SQLTranslationError(
            f"Predicate {term.predicate} expects {len(relation.columns)} arguments, got {len(term.values)}"
        )
    return list(zip(relation.columns, term.values, strict=False))


def relation_from_sql(relation: RelationSpec, context: SQLBuildContext) -> str:
    """Return the SQL relation name used in FROM clauses."""
    if relation.predicate in context.cte_predicates:
        return context.ident(relation.predicate)
    if relation.binding:
        return context.table_ref(relation.binding)
    raise SQLTranslationError(f"Predicate {relation.predicate} has no table binding, facts, or rule")


def sql_column_name(relation: RelationSpec, logical_column: str, context: SQLBuildContext) -> str:
    """Return the column name visible through a relation in the current query."""
    if relation.predicate in context.cte_predicates:
        return logical_column
    return physical_column(relation, logical_column)


def physical_column(relation: RelationSpec, logical_column: str) -> str:
    """Map a logical column to its physical table column."""
    binding = relation.binding
    if not binding or binding.columns is None:
        return logical_column
    if isinstance(binding.columns, Mapping):
        mapped = binding.columns.get(logical_column)
        if mapped is None:
            raise SQLTranslationError(f"No physical column binding for {relation.predicate}.{logical_column}")
        return mapped
    if logical_column not in relation.columns:
        raise SQLTranslationError(f"Unknown logical column {logical_column} for predicate {relation.predicate}")
    index = relation.columns.index(logical_column)
    return str(binding.columns[index])


def null_safe_equals(value: Any) -> str:
    """Return the equality operator for a constant filter."""
    if value is None:
        return "IS"
    return "="


def indent(sql: str, prefix: str = "  ") -> str:
    """Indent a SQL fragment for WITH clauses."""
    return "\n".join(prefix + line if line else line for line in sql.splitlines())
