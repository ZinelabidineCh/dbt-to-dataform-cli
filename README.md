# dbt-to-dataform-cli

**Migrate your dbt project to Dataform (BigQuery) in one command.**

[![CI](https://github.com/ZinelabidineCh/dbt-to-dataform-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/ZinelabidineCh/dbt-to-dataform-cli/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/dbt-to-dataform-cli.svg)](https://pypi.org/project/dbt-to-dataform-cli/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[dbt](https://www.getdbt.com/) (data build tool) has become the default way
to do SQL transformation in a modern ELT pipeline. If your stack runs on
Google Cloud, [Dataform](https://cloud.google.com/dataform) is BigQuery's
native equivalent for analytics engineering — the same ideas (version-controlled
SQL, a dependency graph, built-in tests) without a separate tool to run and
maintain. dbt-to-dataform-cli automates the mechanical, repetitive part of
moving a project from one to the other, straight from the command line.

```bash
pip install dbt-to-dataform-cli
dbt-to-dataform convert path/to/dbt_project -o path/to/dataform_project
```

No web upload, no zip files: point it at a dbt project directory and it
writes a Dataform project next to it, plus a migration report telling you
exactly what was converted automatically and what still needs a manual
pass.

## Why use this

- **A real CLI, not a web app.** `pip install` it, run it locally, wire it
  into a script, a Makefile, or a CI pipeline. Your SQL never leaves your
  machine.
- **Nothing is silently dropped.** Anything the converter can't handle
  (complex Jinja macros, advanced dbt tests, dbt packages) is left in the
  output wrapped in a clear `MANUAL REVIEW NEEDED` marker and listed in the
  migration report — you always know exactly what to check by hand.
- **Validated on a real project.** Every converter is tested end-to-end
  against [jaffle_shop](https://github.com/dbt-labs/jaffle-shop), dbt Labs'
  own reference project — not just unit tests on toy snippets.
- **Actively maintained, with CI.** Lint and the full test suite run
  across Python 3.9–3.12 on Linux and Windows on every commit; see the
  badge above.

## Example

A typical dbt staging model:

```sql
-- models/staging/stg_customers.sql
{{ config(materialized='view') }}

select
    id as customer_id,
    first_name,
    last_name
from {{ source('ecom', 'raw_customers') }}
```

becomes:

```js
// definitions/staging/stg_customers.sqlx
config {
  type: "view"
}

select
    id as customer_id,
    first_name,
    last_name
from ${ref("raw_customers")}
```

— materialization, `ref()`/`source()` calls, and (if declared in
`schema.yml`) `unique`/`not_null` assertions all translated automatically.
See [What it converts](#what-it-converts-mvp-scope) below for the full picture.

## What it converts (MVP scope)

| dbt | Dataform | Status |
|---|---|---|
| `models/**/*.sql` with `{{ ref(...) }}` | `definitions/**/*.sqlx` with `${ref(...)}` | ✅ implemented |
| Materialization config (`table`/`view`/`incremental`) from `dbt_project.yml` and inline `{{ config(...) }}` | `config { type: ... }` block | ✅ implemented |
| `{{ source(...) }}` | `${ref(...)}` | ✅ implemented (flagged for review — verify the source declaration) |
| `sources.yml` | `sources.js` declarations | ✅ implemented |
| `unique` / `not_null` tests in `schema.yml` | `uniqueKey` / `nonNull` assertions | ✅ implemented |
| Migration report (what needs manual review) | `MIGRATION_REPORT.md` | ✅ implemented |

Out of scope for the MVP: dbt packages (`dbt_utils`, ...), complex Jinja
macros (`{% for %}`, `{% if %}`, custom macros), dbt Cloud–specific
features, auto-generated documentation. Anything in this category is left
in the generated file wrapped in a `MANUAL REVIEW NEEDED` marker and listed
in the migration report — never silently dropped.

## Usage

```bash
dbt-to-dataform convert ./my_dbt_project -o ./my_dataform_project
```

Options:

- `-o, --output PATH` — where to write the converted project (default: `./dataform_output`)
- `--dry-run` — run the conversion and print the summary without writing any files

The output layout:

```
my_dataform_project/
  definitions/
    staging/
      stg_customers.sqlx
      ...
    customers.sqlx
    orders.sqlx
    sources.js          # only written if the dbt project has a sources.yml
  MIGRATION_REPORT.md
```

### Sources

Every source table declared under `sources:` in any `schema.yml`/`sources.yml`
becomes a `declare({...})` block in `definitions/sources.js`, keyed by the
dbt source table's `name:` — matching what `{{ source(...) }}` calls get
rewritten to in the converted models. Two things are flagged for manual
review rather than converted automatically:

- **`identifier:` overrides** — Dataform's `declare()` has no separate
  alias concept, so the physical table name is used as `name:`, and you'll
  need to update the generated `${ref(...)}` call in the model(s) that used
  to reference it by its dbt name.
- **`freshness:` checks** — Dataform has no built-in equivalent; recreate
  with a custom assertion if you rely on them.

### Tests

`unique` and `not_null` column tests in `schema.yml` are converted into an
`assertions: { ... }` block nested inside the model's `config { ... }`:

```
config {
  type: "table",
  assertions: {
    uniqueKey: ["customer_id"],
    nonNull: ["customer_id"]
  }
}
```

- `not_null` on multiple columns all collect into one `nonNull` array —
  each check is independent, so this is a direct, lossless mapping.
- `unique` is trickier: Dataform's `assertions.uniqueKey` is a **single
  composite key per model**, while dbt lets every column carry its own
  independent `unique` test. If more than one column has a `unique` test,
  only the first is converted automatically; the rest are flagged for
  manual review (they need their own separate assertion definition).
- Anything beyond `unique`/`not_null` — `accepted_values`, `relationships`,
  custom generic tests, dbt package tests (`dbt_utils`, `dbt_expectations`,
  ...) — is explicitly out of MVP scope and flagged in the migration
  report rather than silently dropped.

## Trying it on a real project

This repo is validated against [jaffle_shop](https://github.com/dbt-labs/jaffle-shop),
dbt Labs' official demo project:

```bash
git clone https://github.com/dbt-labs/jaffle-shop test-input
dbt-to-dataform convert ./test-input -o ./dataform_output
```

## Development

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows
pip install -e ".[dev]"
pytest
ruff check src tests
```

CI runs on every push/PR to `main` ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)):
lint (ruff), tests across Python 3.9–3.12 on Linux and Windows, then a
package build + `twine check` to catch anything that would break `pip install`.

## Roadmap

1. ✅ Model `.sql` -> `.sqlx` conversion, materialization config
2. ✅ `sources.yml` -> `sources.js`
3. ✅ `schema.yml` tests (`unique`, `not_null`) -> assertions
4. 🚧 Richer migration report (HTML output)

## Contributing

Issues and PRs are welcome. This project is intentionally small in scope,
so a good place to start is the [Roadmap](#roadmap) above, or any dbt
project pattern the converters don't handle yet — open an issue with a
minimal repro. Please add a test alongside any change (see `tests/`) and
run `pytest` and `ruff check src tests` before opening a PR.

## License

MIT — see [LICENSE](LICENSE).

## About

Built by [Zinelabidine Chiguer](https://github.com/ZinelabidineCh) —
freelance Data Engineer specializing in BigQuery and Dataform on Google
Cloud. Open to dbt → Dataform migration projects; feel free to reach out
via GitHub.
