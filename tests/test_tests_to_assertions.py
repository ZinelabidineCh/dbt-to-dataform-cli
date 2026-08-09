from dbt_to_dataform.converters.tests_to_assertions import convert


def test_unique_and_not_null_are_converted():
    columns = [{"name": "customer_id", "tests": ["unique", "not_null"]}]
    result = convert(columns)
    assert result.assertions == {"uniqueKey": ["customer_id"], "nonNull": ["customer_id"]}
    assert not result.warnings


def test_not_null_only_columns_are_all_collected():
    columns = [
        {"name": "order_id", "tests": ["unique", "not_null"]},
        {"name": "amount", "tests": ["not_null"]},
        {"name": "status", "tests": []},
    ]
    result = convert(columns)
    assert result.assertions["nonNull"] == ["order_id", "amount"]
    assert result.assertions["uniqueKey"] == ["order_id"]


def test_second_independent_unique_column_is_flagged_not_merged():
    columns = [
        {"name": "order_id", "tests": ["unique"]},
        {"name": "external_id", "tests": ["unique"]},
    ]
    result = convert(columns)
    assert result.assertions["uniqueKey"] == ["order_id"]
    assert len(result.warnings) == 1
    assert "external_id" in result.warnings[0].message


def test_dict_style_test_like_accepted_values_is_flagged():
    columns = [
        {
            "name": "status",
            "tests": [{"accepted_values": {"values": ["placed", "shipped"]}}],
        }
    ]
    result = convert(columns)
    assert result.assertions == {}
    assert len(result.warnings) == 1
    assert "accepted_values" in result.warnings[0].message


def test_relationships_test_is_flagged():
    columns = [
        {
            "name": "customer_id",
            "tests": ["not_null", {"relationships": {"to": "ref('customers')", "field": "customer_id"}}],
        }
    ]
    result = convert(columns)
    assert result.assertions == {"nonNull": ["customer_id"]}
    assert len(result.warnings) == 1
    assert "relationships" in result.warnings[0].message


def test_no_tests_produces_no_assertions():
    columns = [{"name": "first_name"}]
    result = convert(columns)
    assert result.assertions == {}
    assert not result.warnings


def test_empty_columns_list():
    result = convert([])
    assert result.assertions == {}
    assert not result.warnings
