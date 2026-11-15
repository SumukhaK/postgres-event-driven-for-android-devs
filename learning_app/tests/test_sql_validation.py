from learning_app.sql_validation import _identifier_from_diagnostic, validate_sql_suggestions


SCHEMA = {
    "products": ["id", "name", "price", "is_active"],
    "orders": ["id", "customer_id", "status"],
    "customers": ["id", "name"],
}


def test_prose_without_delimited_sql_is_not_applicable():
    result = validate_sql_suggestions("Try filtering active products by their status.", SCHEMA)

    assert result == {"status": "not_applicable", "issues": []}


def test_reports_column_missing_from_schema_without_echoing_query():
    result = validate_sql_suggestions("```sql\nSELECT active FROM products;\n```", SCHEMA)

    assert result["status"] == "issues"
    assert result["issues"][0]["identifier"].lower() == "active"
    assert "SELECT" not in str(result)


def test_extracts_identifier_from_sqlglot_qualify_error_shape():
    # SQLGlot 30.31 emits this shape from validate_qualify_columns().
    assert _identifier_from_diagnostic(
        "Column 'active' could not be resolved. Line: 1, Col: 13"
    ) == "active"


def test_accepts_real_column_and_table_alias():
    result = validate_sql_suggestions(
        "```sql\nSELECT p.is_active FROM products AS p WHERE p.id = 1;\n```", SCHEMA
    )

    assert result == {"status": "clear", "issues": []}


def test_resolves_join_aliases_and_unique_unqualified_column():
    result = validate_sql_suggestions(
        "```sql\nSELECT o.status, c.name FROM orders o "
        "JOIN customers c ON c.id = o.customer_id;\n```",
        SCHEMA,
    )

    assert result == {"status": "clear", "issues": []}


def test_resolves_cte_output_columns():
    result = validate_sql_suggestions(
        "```sql\nWITH active_products AS ("
        "SELECT id, is_active FROM products) "
        "SELECT ap.is_active FROM active_products ap;\n```",
        SCHEMA,
    )

    assert result == {"status": "clear", "issues": []}


def test_reports_unknown_table_as_schema_issue():
    result = validate_sql_suggestions("```sql\nSELECT id FROM inventory;\n```", SCHEMA)

    assert result["status"] == "issues"
    assert result["issues"][0]["identifier"].lower() == "inventory"


def test_ambiguous_column_is_unchecked():
    result = validate_sql_suggestions(
        "```sql\nSELECT id FROM orders o JOIN customers c ON c.id = o.customer_id;\n```",
        SCHEMA,
    )

    assert result["status"] == "unchecked"
    assert result["issues"] == []


def test_malformed_sql_is_unchecked():
    result = validate_sql_suggestions("```sql\nSELECT p. FROM products p;\n```", SCHEMA)

    assert result == {"status": "unchecked", "issues": []}


def test_multiple_statements_are_unchecked():
    result = validate_sql_suggestions("```sql\nSELECT id FROM products; DELETE FROM orders;\n```", SCHEMA)

    assert result == {"status": "unchecked", "issues": []}


def test_update_checks_set_and_predicate_identifiers():
    result = validate_sql_suggestions(
        "```sql\nUPDATE products SET active = false WHERE id = 1;\n```", SCHEMA
    )

    assert result["status"] == "issues"
    assert result["issues"][0]["identifier"].lower() == "active"


def test_accepts_valid_update_with_restrictive_predicate():
    result = validate_sql_suggestions(
        "```sql\nUPDATE products SET is_active = false WHERE id = 1;\n```", SCHEMA
    )

    assert result == {"status": "clear", "issues": []}


def test_non_sql_fence_is_not_inspected():
    result = validate_sql_suggestions("```python\nSELECT active FROM products;\n```", SCHEMA)

    assert result == {"status": "not_applicable", "issues": []}
