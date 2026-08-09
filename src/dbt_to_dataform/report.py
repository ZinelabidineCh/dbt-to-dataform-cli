"""Build the migration report: what was converted automatically, and what
needs a manual pass (complex Jinja, unmapped materializations, etc.)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .warnings import ConversionWarning


@dataclass
class ModelReport:
    name: str
    source_path: str
    output_path: str
    materialized: str
    warnings: list[ConversionWarning] = field(default_factory=list)


@dataclass
class SourcesReport:
    output_path: str = ""
    source_files: list[str] = field(default_factory=list)
    declared: list[str] = field(default_factory=list)
    warnings: list[ConversionWarning] = field(default_factory=list)


@dataclass
class MigrationReport:
    models: list[ModelReport] = field(default_factory=list)
    sources: SourcesReport | None = None

    def add(self, model_report: ModelReport) -> None:
        self.models.append(model_report)

    def set_sources(self, sources_report: SourcesReport) -> None:
        self.sources = sources_report

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

        lines += ["", "## Sources", ""]
        if self.sources is None or not self.sources.declared:
            lines.append("_No `sources.yml` found -- nothing to convert._")
        else:
            files = ", ".join(f"`{f}`" for f in self.sources.source_files)
            lines.append(
                f"Declared {len(self.sources.declared)} source table(s) in "
                f"`{self.sources.output_path}` from {files}:"
            )
            lines.append("")
            for name in self.sources.declared:
                lines.append(f"- `{name}`")
            if self.sources.warnings:
                lines += ["", "Needs manual review:", ""]
                for w in self.sources.warnings:
                    lines.append(f"- {w.message}")

        return "\n".join(lines) + "\n"
