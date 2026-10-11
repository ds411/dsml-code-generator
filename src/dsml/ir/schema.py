# trace: PRD-CORE-022
"""The JSON Schema of the IR, as package data."""

import json
from importlib import resources
from typing import Any, cast

SCHEMA_FILE = "ir.schema.json"
"""The name of the schema file in the package."""


# trace: PRD-CORE-022
def schema_text() -> str:
    """Read the JSON Schema of the IR from the package data."""
    return resources.files("dsml.ir").joinpath(SCHEMA_FILE).read_text(encoding="utf-8")


def load_schema() -> dict[str, Any]:
    """Read the JSON Schema of the IR as JSON data."""
    return cast(dict[str, Any], json.loads(schema_text()))
