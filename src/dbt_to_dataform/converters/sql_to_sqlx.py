"""Convert a dbt model's .sql body into a Dataform .sqlx file.

Handles, in order:
  1. Strip Jinja comments ``{# ... #}``.
  2. Fold an inline ``{{ config(...) }}`` call into the model config (it
     overrides whatever was resolved from dbt_project.yml).
  3. Translate ``{{ ref('model') }}`` -> ``${ref("model")}``.
  4. Translate ``{{ source('src', 'table') }}`` -> ``${ref("table")}``,
     with a warning since it assumes a matching declaration exists.
  5. Translate ``{{ this }}`` -> ``${self()}``.
  6. Translate ``{{ var('x') }}`` -> a Dataform project-variable reference.
  7. Anything else that still looks like Jinja (``{% for %}``, custom
     macros, ``{% if %}``, ...) is left in place but wrapped with a
     visible "MANUAL REVIEW NEEDED" marker and reported as a warning --
     it is explicitly out of scope for the MVP.
  8. Prepend a Dataform ``config { ... }`` header built from the resolved
     materialization / tags / unique_key.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..warnings import ConversionWarning

# --- data types -------------------------------------------------------

@dataclass
class ConversionResult:
    sqlx: str
    config: dict[str, Any] = field(default_factory=dict)
    warnings: list[ConversionWarning] = field(default_factory=list)


# --- regexes ------------------------------------------------------------

_JINJA_COMMENT_RE = re.compile(r"\{#.*?#\}", re.DOTALL)
_CONFIG_CALL_RE = re.compile(r"\{\{\s*config\((?P<args>.*?)\)\s*\}\}", re.DOTALL)
_REF_CALL_RE = re.compile(r"\{\{\s*ref\((?P<args>[^{}]*)\)\s*\}\}")
_SOURCE_CALL_RE = re.compile(r"\{\{\s*source\((?P<args>[^{}]*)\)\s*\}\}")
_VAR_CALL_RE = re.compile(r"\{\{\s*var\((?P<args>[^{}]*)\)\s*\}\}")
_THIS_RE = re.compile(r"\{\{\s*this\s*\}\}")

# whatever Jinja is still left after the substitutions above
_JINJA_BLOCK_RE = re.compile(r"\{%.*?%\}", re.DOTALL)
_JINJA_EXPR_RE = re.compile(r"\{\{.*?\}\}", re.DOTALL)

_QUOTED_ARG_RE = re.compile(r"'([^']*)'|\"([^\"]*)\"")
_CONFIG_KV_RE = re.compile(
    r"(\w+)\s*=\s*(\[[^\]]*\]|'[^']*'|\"[^\"]*\"|true|false|True|False|-?\d+(?:\.\d+)?)"
)

_MATERIALIZED_MAP = {
    "table": "table",
    "view": "view",
    "incremental": "incremental",
}


# --- helpers --------------------------------------------------------------

def _split_quoted_args(args: str) -> list[str]:
    """Extract every quoted string literal from a Jinja call's argument
    list, in order. Good enough for ref()/source()/var(), whose arguments
    are always plain string literals."""
    return [a or b for a, b in _QUOTED_ARG_RE.findall(args)]


def _parse_literal(raw: str) -> Any:
    raw = raw.strip()
    if raw in ("true", "True"):
        return True
    if raw in ("false", "False"):
        return False
    if raw.startswith("[") and raw.endswith("]"):
        return [v.strip().strip("'\"") for v in raw[1:-1].split(",") if v.strip()]
    if raw.startswith(("'", '"')):
        return raw.strip("'\"")
    try:
        return int(raw)
    except ValueError:
        try:
            return float(raw)
        except ValueError:
            return raw


def _parse_config_kwargs(args: str) -> dict[str, Any]:
    return {key: _parse_literal(value) for key, value in _CONFIG_KV_RE.findall(args)}


def _replace_ref(match: re.Match) -> str:
    args = _split_quoted_args(match.group("args"))
    if not args:
        return match.group(0)
    # ref('model') -> model ; ref('package', 'model') -> model (last positional arg)
    model_name = args[-1]
    return f'${{ref("{model_name}")}}'


def _replace_source(match: re.Match, warnings: list[ConversionWarning]) -> str:
    args = _split_quoted_args(match.group("args"))
    if len(args) < 2:
        return match.group(0)
    source_name, table_name = args[0], args[1]
    warnings.append(
        ConversionWarning(
            message=(
                f"source('{source_name}', '{table_name}') was converted to "
                f'${{ref("{table_name}")}}; make sure a matching declaration '
                f'exists in sources.js.'
            )
        )
    )
    return f'${{ref("{table_name}")}}'


def _replace_var(match: re.Match, warnings: list[ConversionWarning]) -> str:
    args = _split_quoted_args(match.group("args"))
    if not args:
        return match.group(0)
    var_name = args[0]
    warnings.append(
        ConversionWarning(
            message=(
                f"var('{var_name}') was converted to a Dataform project "
                f"variable reference; declare '{var_name}' under vars: in "
                f"workflow_settings.yaml."
            )
        )
    )
    return f"${{dataform.projectConfig.vars.{var_name}}}"


def _flag_unsupported_jinja(text: str, warnings: list[ConversionWarning]) -> str:
    def _mark(match: re.Match) -> str:
        snippet = match.group(0).strip()
        warnings.append(
            ConversionWarning(
                message="Unsupported Jinja construct left in place; convert it to JavaScript by hand.",
                snippet=snippet,
            )
        )
        return f"/* dbt-to-dataform: MANUAL REVIEW NEEDED */ {snippet}"

    text = _JINJA_BLOCK_RE.sub(_mark, text)
    text = _JINJA_EXPR_RE.sub(_mark, text)
    return text


def _build_config_block(model_config: dict[str, Any], warnings: list[ConversionWarning]) -> str:
    materialized = model_config.get("materialized", "view")
    dataform_type = _MATERIALIZED_MAP.get(materialized)
    if dataform_type is None:
        warnings.append(
            ConversionWarning(
                message=(
                    f"dbt materialization '{materialized}' has no direct Dataform "
                    f"equivalent; defaulted to 'view' here — review manually."
                )
            )
        )
        dataform_type = "view"

    lines = ["config {", f'  type: "{dataform_type}"']

    if dataform_type == "incremental" and model_config.get("unique_key"):
        unique_key = model_config["unique_key"]
        keys = unique_key if isinstance(unique_key, list) else [unique_key]
        if len(keys) == 1:
            lines.append(f'  uniqueKey: "{keys[0]}"')
        else:
            lines.append("  uniqueKey: [" + ", ".join(f'"{k}"' for k in keys) + "]")

    tags = model_config.get("tags")
    if tags:
        tag_list = tags if isinstance(tags, list) else [tags]
        lines.append("  tags: [" + ", ".join(f'"{t}"' for t in tag_list) + "]")

    schema = model_config.get("schema")
    if schema:
        lines.append(f'  schema: "{schema}"')

    lines.append("}")
    return "\n".join(lines)


# --- public API -------------------------------------------------------

def convert(sql_text: str, model_config: dict[str, Any] | None = None) -> ConversionResult:
    """Convert a dbt model's raw .sql source into Dataform .sqlx content."""
    model_config = dict(model_config or {})
    warnings: list[ConversionWarning] = []

    body = _JINJA_COMMENT_RE.sub("", sql_text)

    def _fold_config(match: re.Match) -> str:
        model_config.update(_parse_config_kwargs(match.group("args")))
        return ""  # the config() call is dropped from the body; it becomes the header instead

    body = _CONFIG_CALL_RE.sub(_fold_config, body)
    body = _REF_CALL_RE.sub(_replace_ref, body)
    body = _SOURCE_CALL_RE.sub(lambda m: _replace_source(m, warnings), body)
    body = _VAR_CALL_RE.sub(lambda m: _replace_var(m, warnings), body)
    body = _THIS_RE.sub("${self()}", body)
    body = _flag_unsupported_jinja(body, warnings)

    body = body.strip("\n")
    # collapse the blank lines left behind by the dropped config() call
    body = re.sub(r"\n{3,}", "\n\n", body)

    config_block = _build_config_block(model_config, warnings)
    sqlx = f"{config_block}\n\n{body}\n"
    return ConversionResult(sqlx=sqlx, config=model_config, warnings=warnings)
