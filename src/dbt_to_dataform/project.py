"""Read a dbt project: load dbt_project.yml, discover model files, and
resolve each model's materialization config using dbt's folder-based
config inheritance (the ``models:`` block in dbt_project.yml)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_MODEL_PATHS = ["models"]

# dbt config keys we know how to translate to Dataform. Anything else set
# under `models:` in dbt_project.yml is ignored for the MVP.
_CONFIG_KEYS = {"materialized", "tags", "unique_key", "schema", "database", "alias"}


class DbtProjectError(Exception):
    """Raised when a directory doesn't look like a usable dbt project."""


@dataclass
class DbtProject:
    name: str
    root: Path
    model_paths: list[str]
    raw_config: dict[str, Any]


def load_dbt_project(root: Path) -> DbtProject:
    """Parse ``dbt_project.yml`` at the root of a dbt project."""
    path = root / "dbt_project.yml"
    if not path.exists():
        raise DbtProjectError(f"No dbt_project.yml found in {root}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    name = raw.get("name")
    if not name:
        raise DbtProjectError(f"{path} is missing the required top-level 'name' key")

    model_paths = raw.get("model-paths") or raw.get("source-paths") or DEFAULT_MODEL_PATHS
    return DbtProject(name=name, root=root, model_paths=model_paths, raw_config=raw)


def discover_models(project: DbtProject) -> list[Path]:
    """Return every ``.sql`` model file under the project's model-paths."""
    files: list[Path] = []
    for model_path in project.model_paths:
        base = project.root / model_path
        if not base.exists():
            continue
        files.extend(sorted(base.rglob("*.sql")))
    return files


def relative_to_models_root(project: DbtProject, model_file: Path) -> Path:
    """Path of a model relative to whichever model-path directory contains it,
    e.g. models/staging/stg_orders.sql -> staging/stg_orders.sql."""
    for model_path in project.model_paths:
        base = (project.root / model_path).resolve()
        try:
            return model_file.resolve().relative_to(base)
        except ValueError:
            continue
    return Path(model_file.name)


def resolve_model_config(project: DbtProject, model_file: Path) -> dict[str, Any]:
    """Resolve a model's materialization config the way dbt does: config
    set at the project level under ``models: <project_name>:`` applies to
    every model, and each subfolder along the model's path can override it.

    Both the legacy syntax (bare keys) and the modern ``+``-prefixed syntax
    are supported::

        models:
          jaffle_shop:
            materialized: table   # legacy, applies to all models
            staging:
              +materialized: view  # modern, overrides for models/staging/**
    """
    models_cfg = project.raw_config.get("models") or {}
    node = models_cfg.get(project.name) or {}

    rel_path = relative_to_models_root(project, model_file)
    folders = list(rel_path.parts[:-1])  # exclude the filename itself

    resolved: dict[str, Any] = _extract_config_keys(node)
    for folder in folders:
        child = node.get(folder, node.get(f"+{folder}"))
        if not isinstance(child, dict):
            break
        node = child
        resolved.update(_extract_config_keys(node))

    resolved.setdefault("materialized", "view")  # dbt's own default
    return resolved


def _extract_config_keys(node: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in node.items():
        clean_key = key[1:] if key.startswith("+") else key
        if clean_key in _CONFIG_KEYS:
            out[clean_key] = value
    return out
