"""Advisory checks for SQL examples against the playground schema.

This module never executes SQL. It checks only explicitly labelled SQL fences;
constructs the parser cannot confidently resolve are reported as unchecked.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from sqlglot import ErrorLevel, exp, parse
from sqlglot.errors import OptimizeError, ParseError
from sqlglot.optimizer.qualify import qualify


_SQL_FENCE = re.compile(
    r"(?ms)^[ \t]*```(?:sql|postgres|postgresql)[ \t]*\r?\n(.*?)^[ \t]*```[ \t]*$",
    re.IGNORECASE,
)
_IDENTIFIER_ERROR = re.compile(
    r"(?:"
    r"(?:unknown|unresolved)\s+(?:column|table|identifier)\s*:?\s*[`\"']?([\w.]+)"
    r"|(?:column|table)\s+[`\"']?([\w.]+)[`\"']?\s+(?:could not be resolved|not found)"
    r")",
    re.IGNORECASE,
)
_MAX_ISSUES = 10


def _schema_columns(schema: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    """Accept either table -> columns or the course's `table (a, b)` strings."""
    normalized: dict[str, dict[str, str]] = {}
    for table, definition in schema.items():
        if isinstance(definition, str):
            match = re.fullmatch(r"\s*[\w\"]+\s*\((.*?)\)\s*", definition, re.DOTALL)
            if not match:
                continue
            columns: Iterable[Any] = match.group(1).split(",")
        elif isinstance(definition, Mapping):
            columns = definition.keys()
        elif isinstance(definition, Iterable):
            columns = definition
        else:
            continue
        normalized[str(table).strip().strip('"').casefold()] = {
            str(column).strip().strip('"'): "UNKNOWN" for column in columns
        }
    return normalized


def _unsupported_statement(statement: exp.Expression) -> bool:
    if isinstance(statement, exp.Query):
        return False
    if isinstance(statement, exp.Update):
        return bool(statement.args.get("from_")) or bool(statement.args.get("returning"))
    if isinstance(statement, exp.Delete):
        return bool(statement.args.get("using")) or bool(statement.args.get("returning"))
    return True


def _identifier_from_diagnostic(diagnostic: str) -> str | None:
    found = _IDENTIFIER_ERROR.search(diagnostic)
    return next((group for group in found.groups() if group), None) if found else None


def _table_identifiers(statement: exp.Expression) -> tuple[list[exp.Table], set[str]]:
    ctes = {cte.alias_or_name.casefold() for cte in statement.find_all(exp.CTE)}
    tables = []
    for table in statement.find_all(exp.Table):
        # Table-valued functions and other non-identifier sources are outside
        # this checker’s supported subset.
        if not isinstance(table.this, exp.Identifier):
            return [], ctes
        if table.name.casefold() not in ctes:
            tables.append(table)
    return tables, ctes


def _unknown_table_issue(statement: exp.Expression, schema: dict[str, dict[str, str]]) -> dict[str, str] | None:
    tables, _ = _table_identifiers(statement)
    if not tables:
        # An empty table list may be a valid SELECT without FROM. The caller
        # separately detects non-identifier table sources as unchecked.
        return None
    known_tables = {name.casefold() for name in schema}
    for table in tables:
        name = table.name
        if name.casefold() not in known_tables:
            return {
                "identifier": name,
                "message": "This table is not present in the playground schema.",
            }
    return None


def _has_unsupported_table_source(statement: exp.Expression) -> bool:
    return any(not isinstance(table.this, exp.Identifier) for table in statement.find_all(exp.Table))


def _ambiguous_unqualified_column(
    statement: exp.Expression,
    identifier: str,
    schema: dict[str, dict[str, str]],
) -> bool:
    tables, _ = _table_identifiers(statement)
    candidates = 0
    for table in tables:
        columns = schema.get(table.name.casefold())
        if columns and identifier.casefold() in {column.casefold() for column in columns}:
            candidates += 1
    return candidates > 1


def _simple_dml_check(
    statement: exp.Expression,
    schema: dict[str, dict[str, str]],
) -> tuple[str, dict[str, str] | None]:
    """Check direct identifiers in simple UPDATE/DELETE statements."""
    if not isinstance(statement, (exp.Update, exp.Delete)):
        return "clear", None
    if any(isinstance(node, exp.Select) for node in statement.walk()):
        return "unchecked", None
    target = statement.this
    if not isinstance(target, exp.Table) or not isinstance(target.this, exp.Identifier):
        return "unchecked", None
    columns = schema.get(target.name.casefold())
    if columns is None:
        return "unchecked", None  # The table check reports this separately.
    known_columns = {column.casefold() for column in columns}
    target_alias = target.alias_or_name.casefold()
    for column in statement.find_all(exp.Column):
        # Simple DML is supported only when column references resolve to the
        # target table. UPDATE FROM and DELETE USING were screened above.
        if column.table and column.table.casefold() not in {target_alias, target.name.casefold()}:
            return "unchecked", None
        if column.name.casefold() not in known_columns:
            return "issues", {
                "identifier": column.name,
                "message": "This column is not present in the playground schema.",
            }
    return "clear", None


def _check_block(sql: str, schema: dict[str, dict[str, str]]) -> tuple[str, list[dict[str, str]]]:
    try:
        statements = parse(sql, read="postgres", error_level=ErrorLevel.RAISE)
    except ParseError:
        return "unchecked", []

    if len(statements) != 1 or statements[0] is None:
        return "unchecked", []
    statement = statements[0]
    if _unsupported_statement(statement):
        return "unchecked", []
    if _has_unsupported_table_source(statement):
        return "unchecked", []

    table_issue = _unknown_table_issue(statement, schema)
    if table_issue:
        return "issues", [table_issue]

    dml_status, dml_issue = _simple_dml_check(statement, schema)
    if dml_status == "unchecked":
        return "unchecked", []
    if dml_issue:
        return "issues", [dml_issue]

    try:
        qualify(
            statement,
            schema=schema,
            dialect="postgres",
            validate_qualify_columns=True,
            identify=False,
            quote_identifiers=False,
        )
    except OptimizeError as error:
        diagnostic = str(error)
        lowered = diagnostic.lower()
        if "ambiguous" in lowered:
            return "unchecked", []
        if not any(marker in lowered for marker in (
            "unknown column", "unknown table", "unresolved", "not found", "could not be resolved"
        )):
            return "unchecked", []
        identifier = _identifier_from_diagnostic(diagnostic)
        if not identifier:
            return "unchecked", []
        if "for table:" not in lowered and _ambiguous_unqualified_column(statement, identifier, schema):
            return "unchecked", []
        return "issues", [{
            "identifier": identifier,
            "message": "This table or column is not present in the playground schema.",
        }]
    except Exception:
        # Optimizer failures outside the known schema diagnostics are not proof
        # that a learner's SQL is invalid.
        return "unchecked", []
    return "clear", []


def validate_sql_suggestions(
    response: str,
    schema: Mapping[str, Any],
) -> dict[str, Any]:
    """Return an advisory status for SQL fences in a tutor response.

    `clear` means all recognized identifiers resolved against the supplied
    schema. It does not establish that the query executes or has correct logic.
    """
    blocks = _SQL_FENCE.findall(response or "")
    if not blocks:
        return {"status": "not_applicable", "issues": []}

    normalized_schema = _schema_columns(schema)
    statuses: list[str] = []
    issues: list[dict[str, str]] = []
    for block in blocks:
        status, block_issues = _check_block(block, normalized_schema)
        statuses.append(status)
        for issue in block_issues:
            if issue not in issues and len(issues) < _MAX_ISSUES:
                issues.append(issue)

    if issues:
        status = "issues"
    elif "unchecked" in statuses:
        status = "unchecked"
    else:
        status = "clear"
    return {"status": status, "issues": issues}
