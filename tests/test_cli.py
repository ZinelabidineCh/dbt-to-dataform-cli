"""End-to-end tests driving the `dbt-to-dataform convert` command through
Click's CliRunner, exercising all three converters together on a small
synthetic dbt project (models, sources.yml, schema.yml tests, and one
unsupported Jinja construct)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from dbt_to_dataform.cli import main

DBT_PROJECT_YML = """
name: 'demo'
model-paths: ["models"]

models:
  demo:
    materialized: view
    staging:
      +materialized: table
"""

SOURCES_YML = """
version: 2
sources:
  - name: ecom
    schema: raw
    tables:
      - name: raw_customers
"""

SCHEMA_YML = """
version: 2
models:
  - name: stg_customers
    columns:
      - name: customer_id
        tests:
          - unique
          - not_null

  - name: customers
    columns:
      - name: customer_id
        tests:
          - unique
          - not_null
      - name: status
        tests:
          - accepted_values:
              values: ['a', 'b']
"""

STG_CUSTOMERS_SQL = "select * from {{ source('ecom', 'raw_customers') }}"

CUSTOMERS_SQL = """\
{% for x in [1, 2] %}
select {{ x }} as n, customer_id from {{ ref('stg_customers') }}
{% endfor %}
"""


@pytest.fixture()
def dbt_project(tmp_path: Path) -> Path:
    root = tmp_path / "dbt_project"
    models = root / "models"
    staging = models / "staging"
    staging.mkdir(parents=True)

    (root / "dbt_project.yml").write_text(DBT_PROJECT_YML, encoding="utf-8")
    (models / "sources.yml").write_text(SOURCES_YML, encoding="utf-8")
    (models / "schema.yml").write_text(SCHEMA_YML, encoding="utf-8")
    (models / "customers.sql").write_text(CUSTOMERS_SQL, encoding="utf-8")
    (staging / "stg_customers.sql").write_text(STG_CUSTOMERS_SQL, encoding="utf-8")
    return root


def test_convert_writes_all_expected_output_files(dbt_project: Path, tmp_path: Path):
    output_dir = tmp_path / "dataform_project"
    runner = CliRunner()
    result = runner.invoke(main, ["convert", str(dbt_project), "-o", str(output_dir)])

    assert result.exit_code == 0, result.output
    assert (output_dir / "definitions" / "customers.sqlx").exists()
    assert (output_dir / "definitions" / "staging" / "stg_customers.sqlx").exists()
    assert (output_dir / "definitions" / "sources.js").exists()
    assert (output_dir / "MIGRATION_REPORT.md").exists()


def test_model_config_and_assertions_flow_through_end_to_end(dbt_project: Path, tmp_path: Path):
    output_dir = tmp_path / "dataform_project"
    runner = CliRunner()
    runner.invoke(main, ["convert", str(dbt_project), "-o", str(output_dir)])

    stg_customers = (output_dir / "definitions" / "staging" / "stg_customers.sqlx").read_text(encoding="utf-8")
    assert 'type: "table"' in stg_customers  # inherited from the staging/ folder override
    assert 'uniqueKey: ["customer_id"]' in stg_customers
    assert 'nonNull: ["customer_id"]' in stg_customers
    assert '${ref("raw_customers")}' in stg_customers  # source() translation

    customers = (output_dir / "definitions" / "customers.sqlx").read_text(encoding="utf-8")
    assert 'type: "view"' in customers  # project-level default, no staging override
    assert '${ref("stg_customers")}' in customers
    assert "MANUAL REVIEW NEEDED" in customers  # the {% for %} loop is left in place, not dropped


def test_sources_js_declares_source_table(dbt_project: Path, tmp_path: Path):
    output_dir = tmp_path / "dataform_project"
    runner = CliRunner()
    runner.invoke(main, ["convert", str(dbt_project), "-o", str(output_dir)])

    sources_js = (output_dir / "definitions" / "sources.js").read_text(encoding="utf-8")
    assert 'schema: "raw"' in sources_js
    assert 'name: "raw_customers"' in sources_js


def test_migration_report_lists_conversions_and_manual_review_items(dbt_project: Path, tmp_path: Path):
    output_dir = tmp_path / "dataform_project"
    runner = CliRunner()
    runner.invoke(main, ["convert", str(dbt_project), "-o", str(output_dir)])

    report = (output_dir / "MIGRATION_REPORT.md").read_text(encoding="utf-8")
    assert "Models converted: 2" in report
    assert "models/staging/stg_customers.sql" in report
    assert "raw_customers" in report
    assert "accepted_values" in report  # flagged, not silently dropped
    assert "Unsupported Jinja construct" in report


def test_console_summary_reports_warning_counts(dbt_project: Path, tmp_path: Path):
    output_dir = tmp_path / "dataform_project"
    runner = CliRunner()
    result = runner.invoke(main, ["convert", str(dbt_project), "-o", str(output_dir)])

    assert "stg_customers" in result.output
    assert "customers" in result.output
    assert "Sources: declared 1 table(s)" in result.output
    assert "Done." in result.output


def test_dry_run_writes_nothing(dbt_project: Path, tmp_path: Path):
    output_dir = tmp_path / "dataform_project"
    runner = CliRunner()
    result = runner.invoke(main, ["convert", str(dbt_project), "-o", str(output_dir), "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "Dry run" in result.output
    assert not output_dir.exists()


def test_missing_dbt_project_yml_fails_clearly(tmp_path: Path):
    empty_dir = tmp_path / "not_a_dbt_project"
    empty_dir.mkdir()
    runner = CliRunner()
    result = runner.invoke(main, ["convert", str(empty_dir)])

    assert result.exit_code != 0
    assert "dbt_project.yml" in result.output


def test_no_models_found_exits_nonzero(tmp_path: Path):
    root = tmp_path / "empty_project"
    root.mkdir()
    (root / "dbt_project.yml").write_text("name: 'demo'\nmodel-paths: [\"models\"]\n", encoding="utf-8")
    (root / "models").mkdir()

    runner = CliRunner()
    result = runner.invoke(main, ["convert", str(root)])

    assert result.exit_code != 0
    assert "No .sql models found" in result.output
