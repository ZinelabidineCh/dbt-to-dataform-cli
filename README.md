# dbt-to-dataform-cli

[![CI](https://github.com/ZinelabidineCh/dbt-to-dataform-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/ZinelabidineCh/dbt-to-dataform-cli/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Convert a [dbt](https://www.getdbt.com/) project into a
[Dataform](https://cloud.google.com/dataform) (BigQuery) project — from the
command line.

```bash
pip install dbt-to-dataform-cli
dbt-to-dataform convert path/to/dbt_project -o path/to/dataform_project
```

No web upload, no zip files: point it at a dbt project directory and it
writes a Dataform project next to it, plus a migration report telling you
exactly what was converted automatically and what still needs a manual
pass.

## Why this exists

Two similar tools already exist: [`ra_dbt_to_dataform`](https://github.com/)
(unmaintained since 2024) and `dbt2dataform` (a web app requiring a zip
upload). Neither is a CLI you can `pip install` and drop into a script,
Makefile, or CI pipeline. This is.

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

## License

MIT — see [LICENSE](LICENSE).
