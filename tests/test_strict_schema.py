"""Structured-output schemas must be accepted by strict providers (Anthropic, OpenAI strict)."""
from homework_coach.intake import OBSERVATION_SCHEMA, RECHECK_SCHEMA, strict_schema


def _walk(s):
    if isinstance(s, dict):
        yield s
        for v in s.values():
            yield from _walk(v)
    elif isinstance(s, list):
        for v in s:
            yield from _walk(v)


def test_every_object_closed_and_no_range_keywords():
    for schema in (OBSERVATION_SCHEMA, RECHECK_SCHEMA):
        s = strict_schema(schema)
        for node in _walk(s):
            if node.get("type") == "object":
                assert node.get("additionalProperties") is False, node
            assert "minimum" not in node and "maximum" not in node
    # property names survive (a property literally called "format" must not be dropped)
    item_props = strict_schema(OBSERVATION_SCHEMA)["properties"]["items"]["items"]["properties"]
    assert "format" in item_props and "confidence" in item_props


def test_original_schema_untouched():
    strict_schema(OBSERVATION_SCHEMA)
    conf = OBSERVATION_SCHEMA["properties"]["items"]["items"]["properties"]["confidence"]
    assert conf.get("maximum") == 1
