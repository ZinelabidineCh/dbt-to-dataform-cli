"""dbt sources.yml -> Dataform sources.js declarations.

Not implemented yet. Planned shape:

    dbt sources.yml:
        sources:
          - name: ecom
            schema: raw
            tables:
              - name: raw_customers

    Dataform sources.js:
        declare({
          database: "my-project",
          schema: "raw",
          name: "raw_customers",
        });

Every dbt {{ source('ecom', 'raw_customers') }} call in a model is already
rewritten to ${ref("raw_customers")} by sql_to_sqlx.convert(); this module
will generate the matching declare() calls so those refs resolve.
"""

from __future__ import annotations


def convert(sources_yml: dict) -> str:
    raise NotImplementedError("sources.yml -> sources.js conversion is planned, not yet implemented")
