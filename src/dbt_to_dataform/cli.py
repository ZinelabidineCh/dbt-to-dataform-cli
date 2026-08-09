"""Entry point for the `dbt-to-dataform` command."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from . import __version__
from .converters.sources_to_js import convert as convert_sources
from .converters.sql_to_sqlx import convert as convert_sql
from .converters.tests_to_assertions import convert as convert_tests
from .project import (
    DbtProjectError,
    discover_models,
    load_dbt_project,
    load_model_tests,
    load_sources,
    relative_to_models_root,
    resolve_model_config,
)
from .report import MigrationReport, ModelReport, SourcesReport
from .writer import write_text

console = Console()


@click.group()
@click.version_option(__version__, prog_name="dbt-to-dataform")
def main() -> None:
    """Convert a dbt project into a Dataform (BigQuery) project."""


@main.command()
@click.argument("input_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    "-o",
    "--output",
    "output_dir",
    type=click.Path(path_type=Path),
    default=Path("dataform_output"),
    show_default=True,
    help="Directory to write the converted Dataform project to.",
)
@click.option("--dry-run", is_flag=True, help="Run the conversion without writing any files.")
def convert(input_dir: Path, output_dir: Path, dry_run: bool) -> None:
    """Convert models in INPUT_DIR (a dbt project) to Dataform .sqlx files.

    Converts model .sql files (models -> definitions/*.sqlx), sources.yml
    (-> definitions/sources.js), and unique/not_null column tests from
    schema.yml (-> assertions in each model's config block). See the
    migration report for what still needs manual work.
    """
    try:
        project = load_dbt_project(input_dir)
    except DbtProjectError as exc:
        raise click.ClickException(str(exc))

    model_files = discover_models(project)
    if not model_files:
        console.print(f"[yellow]No .sql models found under {project.model_paths} in {input_dir}[/yellow]")
        raise SystemExit(1)

    model_tests, _test_files = load_model_tests(project)

    report = MigrationReport()

    for model_file in model_files:
        model_config = resolve_model_config(project, model_file)
        model_name = model_file.stem

        assertion_warnings = []
        columns = model_tests.get(model_name)
        if columns:
            assertions_result = convert_tests(columns)
            if assertions_result.assertions:
                model_config["assertions"] = assertions_result.assertions
            assertion_warnings = assertions_result.warnings

        sql_text = model_file.read_text(encoding="utf-8")
        result = convert_sql(sql_text, model_config)

        rel_path = relative_to_models_root(project, model_file).with_suffix(".sqlx")
        out_path = output_dir / "definitions" / rel_path

        if not dry_run:
            write_text(out_path, result.sqlx)

        report.add(
            ModelReport(
                name=model_name,
                source_path=str(model_file.relative_to(input_dir)).replace("\\", "/"),
                output_path=str(Path("definitions") / rel_path).replace("\\", "/"),
                materialized=result.config.get("materialized", "view"),
                warnings=result.warnings + assertion_warnings,
            )
        )

    source_defs, source_files = load_sources(project)
    if source_defs:
        sources_result = convert_sources(source_defs)
        sources_out_path = Path("definitions") / "sources.js"
        if not dry_run:
            write_text(output_dir / sources_out_path, sources_result.js)
        report.set_sources(
            SourcesReport(
                output_path=str(sources_out_path).replace("\\", "/"),
                source_files=[str(f.relative_to(input_dir)).replace("\\", "/") for f in source_files],
                declared=sources_result.declared,
                warnings=sources_result.warnings,
            )
        )

    if not dry_run:
        write_text(output_dir / "MIGRATION_REPORT.md", report.to_markdown())

    _print_summary(report, output_dir, dry_run)


def _print_summary(report: MigrationReport, output_dir: Path, dry_run: bool) -> None:
    table = Table(title="dbt -> Dataform conversion")
    table.add_column("Model")
    table.add_column("Materialized")
    table.add_column("Status")
    for m in report.models:
        status = "[green]OK[/green]" if not m.warnings else f"[yellow]{len(m.warnings)} warning(s)[/yellow]"
        table.add_row(m.name, m.materialized, status)
    console.print(table)

    if report.sources and report.sources.declared:
        status = "[green]OK[/green]" if not report.sources.warnings else f"[yellow]{len(report.sources.warnings)} warning(s)[/yellow]"
        console.print(f"Sources: declared {len(report.sources.declared)} table(s) in {report.sources.output_path} -- {status}")

    if dry_run:
        console.print("[cyan]Dry run: no files written.[/cyan]")
        return

    console.print(f"[bold green]Done.[/bold green] Wrote {len(report.models)} model(s) to {output_dir / 'definitions'}")
    console.print(f"See {output_dir / 'MIGRATION_REPORT.md'} for what needs a manual review.")


if __name__ == "__main__":
    main()
