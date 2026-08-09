"""dbt schema.yml column tests -> Dataform config-block assertions.

Mapping (MVP scope only):

    dbt schema.yml:
        columns:
          - name: customer_id
            tests:
              - unique
              - not_null

    Dataform config block:
        assertions: {
          uniqueKey: ["customer_id"],
          nonNull: ["customer_id"]
        }

Dataform's ``assertions.uniqueKey`` is a single composite key per model,
unlike dbt where every column can carry its own independent ``unique``
test. When more than one column has a `unique` test, only the first is
converted automatically; the rest are flagged for manual review (they need
their own separate assertion definition).

``not_null`` has no such limitation -- every column with a `not_null` test
is collected into a single `nonNull` array, since each check is
independent.

Anything beyond unique/not_null (accepted_values, relationships, custom
generic tests, dbt packages like dbt_utils/dbt_expectations) is out of MVP
scope and flagged for manual review instead of silently dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..warnings import ConversionWarning


@dataclass
class AssertionsConversionResult:
    assertions: dict[str, list[str]] = field(default_factory=dict)
    warnings: list[ConversionWarning] = field(default_factory=list)


def convert(columns: list[dict[str, Any]]) -> AssertionsConversionResult:
    """``columns`` is the list found under a model's ``columns:`` key in
    schema.yml, already YAML-parsed: ``[{"name": ..., "tests": [...]}]``."""
    warnings: list[ConversionWarning] = []
    unique_columns: list[str] = []
    non_null_columns: list[str] = []

    for column in columns:
        col_name = column.get("name")
        if not col_name:
            continue
        for test in column.get("tests") or []:
            test_name, test_config = _test_name_and_config(test)
            if test_name == "unique":
                unique_columns.append(col_name)
            elif test_name == "not_null":
                non_null_columns.append(col_name)
            else:
                warnings.append(
                    ConversionWarning(
                        message=(
                            f"Test '{test_name}' on column '{col_name}' is out of MVP scope "
                            f"(only unique/not_null are converted automatically); recreate it "
                            f"manually if you rely on it."
                        ),
                        snippet=str(test_config) if test_config is not None else "",
                    )
                )

    assertions: dict[str, list[str]] = {}

    if unique_columns:
        assertions["uniqueKey"] = [unique_columns[0]]
        for extra in unique_columns[1:]:
            warnings.append(
                ConversionWarning(
                    message=(
                        f"Column '{extra}' has its own independent unique test in dbt, but "
                        f"Dataform's assertions block only supports one composite uniqueKey "
                        f"per model (already used for '{unique_columns[0]}'). Add a separate "
                        f"assertion definition for '{extra}' manually."
                    ),
                )
            )

    if non_null_columns:
        assertions["nonNull"] = non_null_columns

    return AssertionsConversionResult(assertions=assertions, warnings=warnings)


def _test_name_and_config(test: Any) -> tuple[str, Any]:
    if isinstance(test, str):
        return test, None
    if isinstance(test, dict) and test:
        name = next(iter(test))
        return name, test[name]
    return "unknown", test
