"""Converters translate one dbt artifact type into its Dataform equivalent.

Implemented:
    - sql_to_sqlx: dbt model .sql -> Dataform .sqlx (models, ref(), config, materialization)

Planned (not yet implemented, see README roadmap):
    - sources_to_js: dbt sources.yml -> Dataform sources.js declarations
    - tests_to_assertions: dbt schema.yml tests (unique, not_null) -> Dataform assertions
"""
