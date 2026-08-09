"""Build the migration report: what was converted automatically, and what
needs a manual pass (complex Jinja, unmapped materializations, etc.)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .converters.sql_to_sqlx import ConversionWarning


@dataclass
class ModelReport:
    name: str
    source_path: str
    output_path: str
    materialized: str
    warnings: list[ConversionWarning] = field(default_factory=list)


@dataclass
class MigrationReport:
    models: list[ModelReport] = field(default_factory=list)

    def add(self, model_report: ModelReport) -> None:
        self.models.append(model_report)

    @property
    def clean(self) -> list[ModelReport]:
        return [m for m in self.models if not m.warnings]

    @property
    def needs_review(self) -> list[ModelReport]:
        return [m for m in self.models if m.warnings]

    def to_markdown(self) -> str:
        lines = [
            "# dbt → Dataform Migration Report",
            "",
            f"- Models converted: {len(self.models)}",
            f"- Converted cleanly: {len(self.clean)}",
            f"- Need manual review: {len(self.needs_review)}",
            "",
            "## Converted automatically",
            "",
        ]
        if self.clean:
            for m in self.clean:
                lines.append(f"- `{m.source_path}` -> `{m.output_path}` (materialized: {m.materialized})")
        else:
            lines.append("_None._")

        lines += ["", "## Needs manual review", ""]
        if self.needs_review:
            for m in self.needs_review:
                lines.append(f"### `{m.source_path}` -> `{m.output_path}`")
                lines.append("")
                for w in m.warnings:
                    lines.append(f"- {w.message}")
                    if w.snippet:
                        lines.append(f"  ```\n  {w.snippet}\n  ```")
                lines.append("")
        else:
            lines.append("_None._")

        return "\n".join(lines) + "\n"
