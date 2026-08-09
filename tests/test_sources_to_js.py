from dbt_to_dataform.converters.sources_to_js import convert

SOURCES = [
    {
        "name": "ecom",
        "schema": "raw",
        "tables": [
            {"name": "raw_customers", "description": "Raw customer records."},
            {"name": "raw_orders"},
        ],
    }
]


def test_declares_one_block_per_table():
    result = convert(SOURCES)
    assert result.declared == ["raw_customers", "raw_orders"]
    assert result.js.count("declare({") == 2
    assert not result.warnings


def test_schema_and_description_are_included():
    result = convert(SOURCES)
    assert 'schema: "raw"' in result.js
    assert 'name: "raw_customers"' in result.js
    assert 'description: "Raw customer records."' in result.js


def test_source_level_database_is_propagated():
    sources = [{"name": "ecom", "schema": "raw", "database": "my-project", "tables": [{"name": "raw_customers"}]}]
    result = convert(sources)
    assert 'database: "my-project"' in result.js


def test_table_level_overrides_win():
    sources = [
        {
            "name": "ecom",
            "schema": "raw",
            "database": "project-a",
            "tables": [{"name": "raw_customers", "schema": "raw_override", "database": "project-b"}],
        }
    ]
    result = convert(sources)
    assert 'schema: "raw_override"' in result.js
    assert 'database: "project-b"' in result.js


def test_identifier_override_is_flagged():
    sources = [
        {
            "name": "ecom",
            "schema": "raw",
            "tables": [{"name": "customers", "identifier": "raw_customers_v2"}],
        }
    ]
    result = convert(sources)
    assert 'name: "raw_customers_v2"' in result.js
    assert len(result.warnings) == 1
    assert "identifier" in result.warnings[0].message


def test_freshness_is_flagged_not_silently_dropped():
    sources = [
        {
            "name": "ecom",
            "schema": "raw",
            "tables": [{"name": "raw_orders", "freshness": {"warn_after": {"count": 12, "period": "hour"}}}],
        }
    ]
    result = convert(sources)
    assert any("Freshness" in w.message for w in result.warnings)


def test_empty_sources_list_produces_no_blocks():
    result = convert([])
    assert result.declared == []
    assert "declare(" not in result.js
