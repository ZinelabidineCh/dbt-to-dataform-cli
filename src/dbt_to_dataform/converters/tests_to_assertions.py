"""dbt schema.yml column tests -> Dataform config-block assertions.

Not implemented yet. Planned mapping (MVP scope only):

    dbt schema.yml:
        columns:
          - name: customer_id
            tests:
              - unique
              - not_null

    Dataform .sqlx config block:
        config {
          type: "table"
          assertions {
            uniqueKey: ["customer_id"]
            nonNull: ["customer_id"]
          }
        }

Anything beyond unique/not_null (accepted_values, relationships, custom
generic tests, dbt packages like dbt_utils/dbt_expectations) is out of MVP
scope and will be listed in the migration report for manual review instead
of silently dropped.
"""

from __future__ import annotations


def convert(model_tests: dict) -> dict:
    raise NotImplementedError("schema.yml tests -> Dataform assertions conversion is planned, not yet implemented")
