"""Entry point for the `dbt-to-dataform` command."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from . import __version__
from .converters.sql_to_sqlx import convert as convert_sql
from .project import DbtProjectError, discover_models, load_dbt_project, relative_to_models_root, resolve_model_config
from .report import MigrationReport, ModelReport
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

    Currently converts model .sql files only (models -> definitions/*.sqlx).
    Sources and tests conversion are planned next -- see the migration
    report for what still needs manual work.
    """
    try:
        project = load_dbt_project(input_dir)
    except DbtProjectError as exc:
        raise click.ClickException(str(exc))

    model_files = discover_models(project)
    if not model_files:
        console.print(f"[yellow]No .sql models found under {project.model_paths} in {input_dir}[/yellow]")
        raise SystemExit(1)

    report = MigrationReport()

    for model_file in model_files:
        model_config = resolve_model_config(project, model_file)
        sql_text = model_file.read_text(encoding="utf-8")
        result = convert_sql(sql_text, model_config)

        rel_path = relative_to_models_root(project, model_file).with_suffix(".sqlx")
        out_path = output_dir / "definitions" / rel_path

        if not dry_run:
            write_text(out_path, result.sqlx)

        report.add(
            ModelReport(
                name=model_file.stem,
                source_path=str(model_file.relative_to(input_dir)).replace("\\", "/"),
                output_path=str(Path("definitions") / rel_path).replace("\\", "/"),
                materialized=result.config.get("materialized", "view"),
                warnings=result.warnings,
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

    if dry_run:
        console.print("[cyan]Dry run: no files written.[/cyan]")
        return

    console.print(f"[bold green]Done.[/bold green] Wrote {len(report.models)} model(s) to {output_dir / 'definitions'}")
    console.print(f"See {output_dir / 'MIGRATION_REPORT.md'} for what needs a manual review.")


if __name__ == "__main__":
    main()
