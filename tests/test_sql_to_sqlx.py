from dbt_to_dataform.converters.sql_to_sqlx import convert


def test_simple_ref_is_translated():
    sql = "select * from {{ ref('stg_customers') }}"
    result = convert(sql, {"materialized": "view"})
    assert '${ref("stg_customers")}' in result.sqlx
    assert "{{" not in result.sqlx
    assert not result.warnings


def test_two_arg_ref_uses_model_name():
    sql = "select * from {{ ref('some_package', 'stg_customers') }}"
    result = convert(sql, {"materialized": "view"})
    assert '${ref("stg_customers")}' in result.sqlx


def test_materialized_config_becomes_header():
    sql = "select 1"
    result = convert(sql, {"materialized": "table"})
    assert 'config {' in result.sqlx
    assert 'type: "table"' in result.sqlx


def test_incremental_with_unique_key():
    sql = "select 1"
    result = convert(sql, {"materialized": "incremental", "unique_key": "order_id"})
    assert 'type: "incremental"' in result.sqlx
    assert 'uniqueKey: "order_id"' in result.sqlx


def test_inline_config_call_overrides_project_config_and_is_stripped():
    sql = "{{ config(materialized='table') }}\nselect 1"
    result = convert(sql, {"materialized": "view"})
    assert 'type: "table"' in result.sqlx
    assert "config(" not in result.sqlx
    assert result.config["materialized"] == "table"


def test_source_call_is_translated_and_flagged():
    sql = "select * from {{ source('ecom', 'raw_customers') }}"
    result = convert(sql, {"materialized": "view"})
    assert '${ref("raw_customers")}' in result.sqlx
    assert len(result.warnings) == 1
    assert "source(" in result.warnings[0].message


def test_this_is_translated():
    sql = "select * from {{ this }}"
    result = convert(sql, {"materialized": "view"})
    assert "${self()}" in result.sqlx


def test_unsupported_jinja_is_flagged_not_silently_dropped():
    sql = "{% for x in [1, 2] %}\nselect {{ x }}\n{% endfor %}"
    result = convert(sql, {"materialized": "view"})
    assert len(result.warnings) >= 1
    assert "MANUAL REVIEW NEEDED" in result.sqlx
    # the original construct is preserved for the user to fix, not deleted
    assert "for x in" in result.sqlx


def test_unknown_materialization_defaults_to_view_with_warning():
    sql = "select 1"
    result = convert(sql, {"materialized": "ephemeral"})
    assert 'type: "view"' in result.sqlx
    assert any("ephemeral" in w.message for w in result.warnings)


def test_jinja_comments_are_stripped():
    sql = "{#- a dbt-only comment -#}\nselect 1"
    result = convert(sql, {"materialized": "view"})
    assert "dbt-only comment" not in result.sqlx
