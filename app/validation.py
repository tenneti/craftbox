"""Dependency-free JSON Schema subset validator and schema registry.

Supports the keywords the Craftbox schemas use. Any other keyword raises, so a schema can never be
silently under-enforced. Schema IDs (e.g. ``filmcraft.scene.v1``) are retained from the prototype.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

SCHEMA_DIR = Path(__file__).parent / "schemas"
CRAFT_DIR = Path(__file__).parent / "crafts"

_ANNOTATIONS = {"$id", "$schema", "title", "description", "$comment", "examples", "default"}
_KEYWORDS = _ANNOTATIONS | {
    "type", "required", "properties", "additionalProperties", "items", "enum", "const",
    "minimum", "maximum", "minLength", "maxLength", "minItems", "maxItems", "pattern", "$ref", "anyOf",
}
_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
}


class SchemaNotFound(KeyError):
    pass


@lru_cache(maxsize=1)
def _registry():
    """Map schema id -> schema: shared artifact schemas plus per-craft input schemas."""
    found = {}
    files = list(SCHEMA_DIR.glob("*.schema.json")) + list(CRAFT_DIR.glob("*/input.schema.json"))
    for path in files:
        schema = json.loads(path.read_text(encoding="utf-8"))
        sid = schema["$id"]
        if sid in found:
            raise RuntimeError(f"duplicate schema id {sid}")
        found[sid] = schema
    return found


def list_schemas():
    return sorted(_registry())


def get_schema(schema_id):
    try:
        return _registry()[schema_id]
    except (KeyError, TypeError):
        raise SchemaNotFound(f"unknown schema {schema_id}") from None


def validate(instance, schema_or_id, max_errors=25):
    """Return a list of ``{"path", "message"}`` dicts; empty means valid."""
    schema = get_schema(schema_or_id) if isinstance(schema_or_id, str) else schema_or_id
    errors = []
    _check(instance, schema, "$", errors, max_errors)
    return errors


def _check(value, schema, path, errors, limit):
    if len(errors) >= limit:
        return

    def fail(message):
        if len(errors) < limit:
            errors.append({"path": path, "message": message})

    unknown = set(schema) - _KEYWORDS
    if unknown:
        raise RuntimeError(f"unsupported schema keyword(s): {sorted(unknown)}")
    if "$ref" in schema:
        _check(value, get_schema(schema["$ref"]), path, errors, limit)
    if "anyOf" in schema and not any(not validate(value, s, 1) for s in schema["anyOf"]):
        fail("does not match any allowed form")
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_TYPES[t](value) for t in types):
            fail(f"expected {' or '.join(types)}, got {_name(value)}")
            return
    if "const" in schema and value != schema["const"]:
        fail(f"must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        fail(f"must be one of {schema['enum']}")
    if _TYPES["number"](value):
        if "minimum" in schema and value < schema["minimum"]:
            fail(f"must be >= {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            fail(f"must be <= {schema['maximum']}")
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            fail(f"must have at least {schema['minLength']} character(s)")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            fail(f"must have at most {schema['maxLength']} character(s)")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            fail(f"must match pattern {schema['pattern']}")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            fail(f"must have at least {schema['minItems']} item(s)")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            fail(f"must have at most {schema['maxItems']} item(s)")
        if "items" in schema:
            for i, item in enumerate(value):
                _check(item, schema["items"], f"{path}[{i}]", errors, limit)
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                fail(f"missing required property '{name}'")
        for name, item in value.items():
            if name in props:
                _check(item, props[name], f"{path}.{name}", errors, limit)
            elif schema.get("additionalProperties") is False:
                fail(f"unexpected property '{name}'")
            elif isinstance(schema.get("additionalProperties"), dict):
                _check(item, schema["additionalProperties"], f"{path}.{name}", errors, limit)


def _name(value):
    return "null" if value is None else type(value).__name__
