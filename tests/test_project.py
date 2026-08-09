from pathlib import Path

import pytest

from dbt_to_dataform.project import (
    DbtProjectError,
    discover_models,
    load_dbt_project,
    resolve_model_config,
)

DBT_PROJECT_YML = """
name: 'jaffle_shop'
config-version: 2
version: '0.1'
profile: 'jaffle_shop'
model-paths: ["models"]

models:
  jaffle_shop:
      materialized: table
      staging:
        materialized: view
"""


@pytest.fixture()
def dbt_project_dir(tmp_path: Path) -> Path:
    (tmp_path / "dbt_project.yml").write_text(DBT_PROJECT_YML, encoding="utf-8")
    models = tmp_path / "models"
    staging = models / "staging"
    staging.mkdir(parents=True)
    (models / "customers.sql").write_text("select 1", encoding="utf-8")
    (staging / "stg_customers.sql").write_text("select 1", encoding="utf-8")
    return tmp_path


def test_load_dbt_project_reads_name(dbt_project_dir: Path):
    project = load_dbt_project(dbt_project_dir)
    assert project.name == "jaffle_shop"
    assert project.model_paths == ["models"]


def test_load_dbt_project_missing_file_raises(tmp_path: Path):
    with pytest.raises(DbtProjectError):
        load_dbt_project(tmp_path)


def test_discover_models_finds_all_sql_files(dbt_project_dir: Path):
    project = load_dbt_project(dbt_project_dir)
    models = discover_models(project)
    names = {m.name for m in models}
    assert names == {"customers.sql", "stg_customers.sql"}


def test_top_level_model_gets_project_materialization(dbt_project_dir: Path):
    project = load_dbt_project(dbt_project_dir)
    model_file = dbt_project_dir / "models" / "customers.sql"
    config = resolve_model_config(project, model_file)
    assert config["materialized"] == "table"


def test_subfolder_overrides_project_materialization(dbt_project_dir: Path):
    project = load_dbt_project(dbt_project_dir)
    model_file = dbt_project_dir / "models" / "staging" / "stg_customers.sql"
    config = resolve_model_config(project, model_file)
    assert config["materialized"] == "view"
