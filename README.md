# dbt-to-dataform-cli

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
| `sources.yml` | `sources.js` declarations | 🚧 planned |
| `unique` / `not_null` tests in `schema.yml` | `uniqueKey` / `nonNull` assertions | 🚧 planned |
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
  MIGRATION_REPORT.md
```

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
```

## Roadmap

1. ✅ Model `.sql` -> `.sqlx` conversion, materialization config
2. 🚧 `sources.yml` -> `sources.js`
3. 🚧 `schema.yml` tests (`unique`, `not_null`) -> assertions
4. 🚧 Richer migration report (HTML output)

## License

MIT — see [LICENSE](LICENSE).
