"""Thorough unit tests for MCP pure helper modules.

Covers:
- ``app/services/mcp/result_normalizer.py`` (primary): content coercion,
  text extraction, embedded JSON extraction, number coercion, table/keyword
  normalization, and the full Sorftime tool dispatch + summary logic.
- ``app/services/mcp/schema_utils.py`` (secondary): JSON Schema filtering,
  Gemini/OpenAI conversion, type normalization, and schema validation.

These are pure functions with no external boundaries, so no mocking of
network/SDK/DB is required. Inputs are plain in-memory objects.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.services.mcp import result_normalizer as rn
from app.services.mcp import schema_utils as su


# ---------------------------------------------------------------------------
# result_normalizer._truncate
# ---------------------------------------------------------------------------


def test_truncate_returns_stripped_value_when_short():
    assert rn._truncate("  hello  ") == "hello"


def test_truncate_handles_none_and_empty():
    assert rn._truncate(None) == ""
    assert rn._truncate("") == ""


def test_truncate_appends_ellipsis_when_over_limit():
    long_text = "x" * 300
    result = rn._truncate(long_text, max_chars=240)
    assert result.endswith("...")
    # 240 chars + the literal ellipsis
    assert len(result) == 243
    assert result[:240] == "x" * 240


def test_truncate_respects_custom_max_chars():
    result = rn._truncate("abcdef", max_chars=3)
    assert result == "abc..."


def test_truncate_coerces_non_string_input():
    assert rn._truncate(12345) == "12345"


# ---------------------------------------------------------------------------
# result_normalizer._coerce_content_item
# ---------------------------------------------------------------------------


def test_coerce_content_item_from_dict_uses_text():
    item = {"type": "text", "text": "hi", "annotations": {"a": 1}, "meta": {"m": 2}}
    out = rn._coerce_content_item(item)
    assert out == {
        "type": "text",
        "text": "hi",
        "annotations": {"a": 1},
        "meta": {"m": 2},
    }


def test_coerce_content_item_from_dict_falls_back_to_content_key():
    item = {"content": "from-content"}
    out = rn._coerce_content_item(item)
    assert out["type"] == "unknown"
    assert out["text"] == "from-content"
    assert out["annotations"] is None
    assert out["meta"] is None


def test_coerce_content_item_from_dict_empty_text():
    out = rn._coerce_content_item({"type": "image"})
    assert out["type"] == "image"
    assert out["text"] == ""


def test_coerce_content_item_from_object_with_attributes():
    obj = SimpleNamespace(type="text", text="obj-text", annotations=["a"], meta={"k": "v"})
    out = rn._coerce_content_item(obj)
    assert out == {
        "type": "text",
        "text": "obj-text",
        "annotations": ["a"],
        "meta": {"k": "v"},
    }


def test_coerce_content_item_from_object_with_only_type():
    obj = SimpleNamespace(type="resource", text=None, annotations=None, meta=None)
    out = rn._coerce_content_item(obj)
    assert out["type"] == "resource"
    assert out["text"] == ""


def test_coerce_content_item_fallback_to_str_repr():
    # A bare object with none of the recognized attributes -> stringified.
    out = rn._coerce_content_item(42)
    assert out["type"] == "int"
    assert out["text"] == "42"
    assert out["annotations"] is None
    assert out["meta"] is None


def test_coerce_content_item_object_text_none_type_none_falls_through():
    class Bare:
        text = None
        type = None
        annotations = None
        meta = None

        def __str__(self):
            return "bare-repr"

    out = rn._coerce_content_item(Bare())
    assert out["type"] == "Bare"
    assert out["text"] == "bare-repr"


# ---------------------------------------------------------------------------
# result_normalizer.coerce_mcp_content
# ---------------------------------------------------------------------------


def test_coerce_mcp_content_none_returns_empty_list():
    assert rn.coerce_mcp_content(None) == []


def test_coerce_mcp_content_list_maps_each_item():
    out = rn.coerce_mcp_content([{"text": "a"}, {"text": "b"}])
    assert [i["text"] for i in out] == ["a", "b"]


def test_coerce_mcp_content_single_item_wrapped_in_list():
    out = rn.coerce_mcp_content({"text": "solo"})
    assert isinstance(out, list)
    assert len(out) == 1
    assert out[0]["text"] == "solo"


# ---------------------------------------------------------------------------
# result_normalizer.extract_text_segments
# ---------------------------------------------------------------------------


def test_extract_text_segments_skips_empty_and_strips():
    out = rn.extract_text_segments([{"text": "  one  "}, {"text": ""}, {"text": "two"}])
    assert out == ["one", "two"]


def test_extract_text_segments_none_returns_empty():
    assert rn.extract_text_segments(None) == []


# ---------------------------------------------------------------------------
# result_normalizer.extract_embedded_json
# ---------------------------------------------------------------------------


def test_extract_embedded_json_empty_returns_none():
    assert rn.extract_embedded_json("") is None
    assert rn.extract_embedded_json(None) is None
    assert rn.extract_embedded_json("   ") is None


def test_extract_embedded_json_parses_pure_object():
    assert rn.extract_embedded_json('{"a": 1}') == {"a": 1}


def test_extract_embedded_json_parses_pure_array():
    assert rn.extract_embedded_json('[1, 2, 3]') == [1, 2, 3]


def test_extract_embedded_json_finds_json_inside_prose():
    text = 'Here is the data: {"key": "value"} trailing words'
    assert rn.extract_embedded_json(text) == {"key": "value"}


def test_extract_embedded_json_skips_invalid_brace_then_finds_valid():
    # The first '{' starts an invalid fragment; the parser advances to the next.
    text = 'noise { not json } then [10, 20]'
    assert rn.extract_embedded_json(text) == [10, 20]


def test_extract_embedded_json_returns_none_when_no_valid_json():
    assert rn.extract_embedded_json("no braces or brackets here") is None


def test_extract_embedded_json_nested_structure():
    text = 'prefix {"outer": {"inner": [1, 2]}} suffix'
    assert rn.extract_embedded_json(text) == {"outer": {"inner": [1, 2]}}


# ---------------------------------------------------------------------------
# result_normalizer._to_number
# ---------------------------------------------------------------------------


def test_to_number_parses_int():
    assert rn._to_number("42") == 42


def test_to_number_parses_float():
    assert rn._to_number("3.14") == 3.14


def test_to_number_strips_thousands_separators():
    assert rn._to_number("1,234") == 1234
    assert rn._to_number("1,234.5") == 1234.5


def test_to_number_returns_original_for_empty():
    assert rn._to_number("") == ""
    assert rn._to_number(None) is None


def test_to_number_returns_original_for_non_numeric():
    assert rn._to_number("abc") == "abc"
    assert rn._to_number("12abc") == "12abc"


def test_to_number_handles_numeric_value_passthrough_when_unparseable():
    # A value like "1.2.3" cannot be parsed -> returned unchanged.
    assert rn._to_number("1.2.3") == "1.2.3"


# ---------------------------------------------------------------------------
# result_normalizer._normalize_table_rows
# ---------------------------------------------------------------------------


def test_normalize_table_rows_non_list_returns_empty():
    assert rn._normalize_table_rows({"not": "a list"}, {"k": "v"}) == []
    assert rn._normalize_table_rows(None, {}) == []


def test_normalize_table_rows_maps_and_converts():
    rows = [{"Name": "Widget", "Count": "12"}]
    out = rn._normalize_table_rows(rows, {"Name": "name", "Count": "count"})
    assert out == [{"name": "Widget", "count": 12}]


def test_normalize_table_rows_skips_non_dict_rows():
    rows = [{"A": "1"}, "string-row", 99, {"A": "2"}]
    out = rn._normalize_table_rows(rows, {"A": "a"})
    assert out == [{"a": 1}, {"a": 2}]


def test_normalize_table_rows_skips_missing_keys_and_empty_items():
    rows = [{"Other": "x"}, {"A": "5"}]
    out = rn._normalize_table_rows(rows, {"A": "a"})
    # First row has no mapped key -> produces empty item -> skipped.
    assert out == [{"a": 5}]


# ---------------------------------------------------------------------------
# result_normalizer._parse_product_detail_text
# ---------------------------------------------------------------------------


def test_parse_product_detail_text_uses_fullwidth_colon():
    text = "标题：Cool Gadget\n价格：19.99\n品牌：Acme"
    out = rn._parse_product_detail_text(text)
    assert out["标题"] == "Cool Gadget"
    assert out["价格"] == 19.99
    assert out["品牌"] == "Acme"


def test_parse_product_detail_text_skips_lines_without_colon():
    text = "no colon line\n标题：X"
    out = rn._parse_product_detail_text(text)
    assert out == {"标题": "X"}


def test_parse_product_detail_text_skips_empty_field_or_value():
    text = "：orphan-value\n标题：\n品牌：Y"
    out = rn._parse_product_detail_text(text)
    assert out == {"品牌": "Y"}


def test_parse_product_detail_text_empty_input():
    assert rn._parse_product_detail_text("") == {}
    assert rn._parse_product_detail_text(None) == {}


# ---------------------------------------------------------------------------
# result_normalizer._normalize_keyword_trend
# ---------------------------------------------------------------------------


def test_normalize_keyword_trend_non_dict_returns_none():
    assert rn._normalize_keyword_trend(["not", "dict"]) is None
    assert rn._normalize_keyword_trend(None) is None


def test_normalize_keyword_trend_builds_series():
    parsed = {
        "关键词": "wireless mouse",
        "搜索量趋势": ["100", "150"],
        "搜索排名趋势": ["3", ""],  # empty point skipped
        "推荐竞价趋势": "not-a-list",  # ignored
    }
    out = rn._normalize_keyword_trend(parsed)
    assert out is not None
    assert out["kind"] == "time_series"
    assert out["keyword"] == "wireless mouse"
    metrics = {s["metric"]: s for s in out["series"]}
    assert "search_volume" in metrics
    assert metrics["search_volume"]["points"] == [{"label": "100"}, {"label": "150"}]
    assert "search_rank" in metrics
    assert metrics["search_rank"]["points"] == [{"label": "3"}]
    assert "recommended_cpc" not in metrics


def test_normalize_keyword_trend_no_series_returns_none():
    # All series lists empty -> no points -> returns None.
    parsed = {"关键词": "x", "搜索量趋势": ["", "  "]}
    assert rn._normalize_keyword_trend(parsed) is None


def test_normalize_keyword_trend_empty_dict_returns_none():
    assert rn._normalize_keyword_trend({}) is None


# ---------------------------------------------------------------------------
# result_normalizer.normalize_sorftime_result - dispatch branches
# ---------------------------------------------------------------------------


def _content(text: str):
    return [{"type": "text", "text": text}]


def test_normalize_sorftime_category_name_search():
    payload = '[{"Name": "Electronics", "NodeId": "172282"}, {"Name": "Audio", "NodeId": "999"}]'
    out = rn.normalize_sorftime_result("category_name_search", _content(payload))
    assert out["normalized"]["kind"] == "category_matches"
    items = out["normalized"]["items"]
    assert items[0] == {"name": "Electronics", "nodeId": 172282}
    assert "匹配到 2 个类目" in out["text"]
    assert "Electronics" in out["text"]


def test_normalize_sorftime_category_name_search_empty_items_summary():
    # Valid empty list -> category_matches with zero items, summary handles first={}.
    out = rn.normalize_sorftime_result("category_name_search", _content("[]"))
    assert out["normalized"]["kind"] == "category_matches"
    assert out["normalized"]["items"] == []
    assert "匹配到 0 个类目" in out["text"]
    assert "unknown" in out["text"]


def test_normalize_sorftime_category_report():
    payload = (
        '{"Top100产品": [{"ASIN": "B001", "标题": "Thing", "月销量": "1,200", '
        '"品牌": "Acme", "价格": "29.99"}]}'
    )
    out = rn.normalize_sorftime_result("category_report", _content(payload))
    assert out["normalized"]["kind"] == "category_report"
    item = out["normalized"]["items"][0]
    assert item["asin"] == "B001"
    assert item["monthlySales"] == 1200
    assert item["price"] == 29.99
    assert "返回类目 Top 产品 1 条" in out["text"]
    assert "B001" in out["text"]


def test_normalize_sorftime_table_kind_for_product_search():
    payload = '[{"关键词": "mouse", "周搜索量": "5,000", "价格": "12.50"}]'
    out = rn.normalize_sorftime_result("product_search", _content(payload))
    assert out["normalized"]["kind"] == "table"
    item = out["normalized"]["items"][0]
    assert item["keyword"] == "mouse"
    assert item["weeklySearchVolume"] == 5000
    assert item["price"] == 12.5
    assert "返回结构化表格数据 1 条" in out["text"]


def test_normalize_sorftime_table_kind_for_other_table_tools():
    for tool in ("category_keywords", "product_traffic_terms", "competitor_product_keywords"):
        payload = '[{"关键词": "kw", "月搜索量": "10"}]'
        out = rn.normalize_sorftime_result(tool, _content(payload))
        assert out["normalized"]["kind"] == "table", tool
        assert out["normalized"]["items"][0]["monthlySearchVolume"] == 10


def test_normalize_sorftime_keyword_trend():
    payload = '{"关键词": "kw", "搜索量趋势": ["1", "2", "3"]}'
    out = rn.normalize_sorftime_result("keyword_trend", _content(payload))
    assert out["normalized"]["kind"] == "time_series"
    assert "返回关键词趋势序列 1 条" in out["text"]
    assert "共 3 个时间点" in out["text"]


def test_normalize_sorftime_keyword_trend_none_normalized_falls_back_to_text():
    # keyword_trend dispatch returns None when embedded json has no usable series.
    out = rn.normalize_sorftime_result("keyword_trend", _content("just some plain text"))
    assert out["normalized"] is None
    # Falls back to truncated full_text as summary.
    assert out["text"] == "just some plain text"


def test_normalize_sorftime_product_detail():
    text = "标题：Mega Widget\n品牌：Acme\n价格：49.99"
    out = rn.normalize_sorftime_result("product_detail", _content(text))
    assert out["normalized"]["kind"] == "product_detail"
    details = out["normalized"]["details"]
    assert details["标题"] == "Mega Widget"
    assert "产品详情已获取" in out["text"]
    assert "Mega Widget" in out["text"]
    assert "Acme" in out["text"]


def test_normalize_sorftime_product_detail_no_details_falls_back():
    # No fullwidth colons -> _parse_product_detail_text returns {} -> normalized None.
    out = rn.normalize_sorftime_result("product_detail", _content("no parseable fields"))
    assert out["normalized"] is None
    assert out["text"] == "no parseable fields"


def test_normalize_sorftime_unknown_tool_falls_back_to_truncated_text():
    out = rn.normalize_sorftime_result("totally_unknown_tool", _content("some output text"))
    assert out["normalized"] is None
    assert out["text"] == "some output text"


def test_normalize_sorftime_empty_result_default_summary():
    out = rn.normalize_sorftime_result("unknown", None)
    assert out["content"] == []
    assert out["text"] == "MCP 工具调用完成。"
    assert out["parsed"] is None
    assert out["normalized"] is None
    assert out["rawText"] == ""


def test_normalize_sorftime_category_name_search_wrong_json_type_no_normalize():
    # Tool expects a list but embedded json is a dict -> no normalization branch.
    out = rn.normalize_sorftime_result("category_name_search", _content('{"a": 1}'))
    assert out["normalized"] is None
    assert out["parsed"] == {"a": 1}


def test_normalize_sorftime_tool_name_is_case_insensitive_and_trimmed():
    payload = '[{"Name": "X", "NodeId": "1"}]'
    out = rn.normalize_sorftime_result("  CATEGORY_NAME_SEARCH  ", _content(payload))
    assert out["normalized"]["kind"] == "category_matches"


def test_normalize_sorftime_content_item_truncates_each_segment_to_240():
    # Each content item's text is truncated to 240 chars during coercion, so a
    # single huge segment cannot reach the 4000-char rawText cap on its own.
    big = "标题：" + ("Z" * 5000)
    out = rn.normalize_sorftime_result("product_detail", _content(big))
    assert out["rawText"].endswith("...")
    assert len(out["rawText"]) == 243  # 240 chars + literal ellipsis


def test_normalize_sorftime_rawtext_capped_at_4000_across_many_segments():
    # full_text joins many 240-char segments; the rawText cap of 4000 applies.
    segments = [{"type": "text", "text": "A" * 240} for _ in range(40)]
    out = rn.normalize_sorftime_result("unknown_tool", segments)
    assert out["rawText"].endswith("...")
    assert len(out["rawText"]) == 4003  # 4000 chars + literal ellipsis


def test_normalize_sorftime_picks_first_segment_with_json():
    # First segment has no json, second has the array.
    result = [
        {"type": "text", "text": "preamble without json"},
        {"type": "text", "text": '[{"Name": "Found", "NodeId": "7"}]'},
    ]
    out = rn.normalize_sorftime_result("category_name_search", result)
    assert out["normalized"]["items"][0]["name"] == "Found"
    assert out["parsed"] == [{"Name": "Found", "NodeId": "7"}]


# ---------------------------------------------------------------------------
# schema_utils._canonicalize_schema_field
# ---------------------------------------------------------------------------


def test_canonicalize_schema_field_maps_aliases():
    assert su._canonicalize_schema_field("any_of") == "anyOf"
    assert su._canonicalize_schema_field("one_of") == "oneOf"
    assert su._canonicalize_schema_field("all_of") == "allOf"


def test_canonicalize_schema_field_passthrough_unknown():
    assert su._canonicalize_schema_field("type") == "type"
    assert su._canonicalize_schema_field("custom") == "custom"


# ---------------------------------------------------------------------------
# schema_utils.filter_supported_schema
# ---------------------------------------------------------------------------


def test_filter_supported_schema_non_dict_passthrough():
    assert su.filter_supported_schema("not-a-dict") == "not-a-dict"
    assert su.filter_supported_schema([1, 2]) == [1, 2]


def test_filter_supported_schema_removes_unsupported_fields():
    schema = {"type": "object", "unknown_field": "drop me", "title": "keep"}
    out = su.filter_supported_schema(schema)
    assert "unknown_field" not in out
    assert out["type"] == "object"
    assert out["title"] == "keep"


def test_filter_supported_schema_recurses_into_items_dict():
    schema = {
        "type": "array",
        "items": {"type": "string", "junk": "x"},
    }
    out = su.filter_supported_schema(schema)
    assert out["items"] == {"type": "string"}


def test_filter_supported_schema_items_non_dict_preserved():
    schema = {"type": "array", "items": ["literal"]}
    out = su.filter_supported_schema(schema)
    assert out["items"] == ["literal"]


def test_filter_supported_schema_canonicalizes_and_recurses_list_fields():
    schema = {
        "any_of": [
            {"type": "string", "bad": 1},
            {"type": "integer"},
            "literal-not-dict",
        ]
    }
    out = su.filter_supported_schema(schema)
    assert "anyOf" in out
    assert out["anyOf"][0] == {"type": "string"}
    assert out["anyOf"][1] == {"type": "integer"}
    assert out["anyOf"][2] == "literal-not-dict"


def test_filter_supported_schema_list_field_non_list_preserved():
    schema = {"anyOf": "not-a-list"}
    out = su.filter_supported_schema(schema)
    assert out["anyOf"] == "not-a-list"


def test_filter_supported_schema_recurses_into_properties():
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "remove": True},
            "literal": "not-a-dict",
        },
    }
    out = su.filter_supported_schema(schema)
    assert out["properties"]["name"] == {"type": "string"}
    assert out["properties"]["literal"] == "not-a-dict"


def test_filter_supported_schema_dict_field_non_dict_preserved():
    schema = {"properties": "weird"}
    out = su.filter_supported_schema(schema)
    assert out["properties"] == "weird"


def test_filter_supported_schema_preserves_plain_supported_fields():
    schema = {"type": "string", "enum": ["a", "b"], "default": "a", "pattern": "^a"}
    out = su.filter_supported_schema(schema)
    assert out == schema


# ---------------------------------------------------------------------------
# schema_utils.mcp_schema_to_gemini_schema
# ---------------------------------------------------------------------------


def test_mcp_schema_to_gemini_lowercases_type():
    schema = {"type": "OBJECT", "properties": {"x": {"type": "STRING"}}}
    out = su.mcp_schema_to_gemini_schema(schema)
    assert out["type"] == "object"
    # Nested types are not lowercased by this function (only top-level).
    assert out["properties"]["x"]["type"] == "STRING"


def test_mcp_schema_to_gemini_filters_and_keeps_required():
    schema = {
        "type": "object",
        "properties": {"location": {"type": "string", "description": "City"}},
        "required": ["location"],
        "$comment": "drop",
    }
    out = su.mcp_schema_to_gemini_schema(schema)
    assert out["required"] == ["location"]
    assert "$comment" not in out


def test_mcp_schema_to_gemini_no_type_key():
    schema = {"properties": {"a": {"type": "string"}}}
    out = su.mcp_schema_to_gemini_schema(schema)
    assert "type" not in out
    assert out["properties"]["a"]["type"] == "string"


# ---------------------------------------------------------------------------
# schema_utils.mcp_schema_to_openai_schema
# ---------------------------------------------------------------------------


def test_mcp_schema_to_openai_filters_unsupported():
    schema = {"type": "object", "properties": {}, "weird": 1}
    out = su.mcp_schema_to_openai_schema(schema)
    assert "weird" not in out
    # OpenAI conversion does NOT lowercase type (unlike gemini).
    assert out["type"] == "object"


def test_mcp_schema_to_openai_preserves_uppercase_type():
    schema = {"type": "OBJECT"}
    out = su.mcp_schema_to_openai_schema(schema)
    assert out["type"] == "OBJECT"


# ---------------------------------------------------------------------------
# schema_utils.normalize_schema_type
# ---------------------------------------------------------------------------


def test_normalize_schema_type_known_uppercase():
    assert su.normalize_schema_type("STRING") == "string"
    assert su.normalize_schema_type("OBJECT") == "object"
    assert su.normalize_schema_type("ARRAY") == "array"
    assert su.normalize_schema_type("NULL") == "null"


def test_normalize_schema_type_mixed_case_resolves_via_upper():
    assert su.normalize_schema_type("Integer") == "integer"
    assert su.normalize_schema_type("boolean") == "boolean"


def test_normalize_schema_type_unknown_lowercased():
    assert su.normalize_schema_type("CustomType") == "customtype"


# ---------------------------------------------------------------------------
# schema_utils.validate_schema
# ---------------------------------------------------------------------------


def test_validate_schema_non_dict_returns_error():
    assert su.validate_schema("not-a-dict") == ["Schema must be an object"]


def test_validate_schema_valid_object_no_errors():
    assert su.validate_schema({"type": "object", "properties": {}}) == []


def test_validate_schema_missing_type_and_ref_and_composite():
    errors = su.validate_schema({"description": "no type"})
    assert "Schema must have 'type' field" in errors


def test_validate_schema_ref_satisfies_type_requirement():
    assert su.validate_schema({"$ref": "#/$defs/Foo"}) == []


def test_validate_schema_composite_field_satisfies_type_requirement():
    schema = {"anyOf": [{"type": "string"}, {"type": "integer"}]}
    assert su.validate_schema(schema) == []


def test_validate_schema_array_without_items_errors():
    errors = su.validate_schema({"type": "array"})
    assert "Array type schema must have 'items' field" in errors


def test_validate_schema_array_with_items_ok():
    assert su.validate_schema({"type": "array", "items": {"type": "string"}}) == []


def test_validate_schema_object_without_properties_no_error_only_warns():
    # Missing properties on an object only logs a warning, not an error.
    errors = su.validate_schema({"type": "object"})
    assert errors == []


def test_validate_schema_composite_field_not_list_errors():
    errors = su.validate_schema({"anyOf": {"type": "string"}})
    assert "'anyOf' field must be a list" in errors


def test_validate_schema_ref_not_string_errors():
    errors = su.validate_schema({"$ref": 123})
    assert "'$ref' field must be a string" in errors


def test_validate_schema_required_not_list_errors():
    errors = su.validate_schema({"type": "object", "properties": {}, "required": "name"})
    assert "'required' field must be a list" in errors


def test_validate_schema_required_field_not_in_properties_errors():
    schema = {
        "type": "object",
        "properties": {"a": {"type": "string"}},
        "required": ["a", "missing"],
    }
    errors = su.validate_schema(schema)
    assert "Required field 'missing' not in properties" in errors
    assert not any("'a'" in e for e in errors)


def test_validate_schema_required_all_present_no_error():
    schema = {
        "type": "object",
        "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
        "required": ["a", "b"],
    }
    assert su.validate_schema(schema) == []


def test_validate_schema_canonicalizes_snake_case_composite_input():
    # any_of (snake_case) should be canonicalized to anyOf during validation,
    # satisfying the "must have type" requirement.
    schema = {"any_of": [{"type": "string"}]}
    assert su.validate_schema(schema) == []
