# trace: PRD-TRACE-015
"""The hash of the IR form of an element.

The impact and suspect reports compare these hashes with the hashes of a
baseline. An element is changed if its hash is different (PRD-TRACE-015).
A source location is not part of the hash. Thus a change of the location of
an element only, for example a new line above it, does not change its hash.
"""

import hashlib

from dsml.ir.model import Element, Ir
from dsml.ir.writer import JsonValue, canonical_json, to_data

_LOCATION_KEY = "location"


# trace: PRD-TRACE-015, PRD-CORE-028
def element_hash(element: Element) -> str:
    """Give the SHA-256 of the canonical JSON of the element with no source locations.

    The result is 64 lowercase hexadecimal characters.
    """
    data = _without_locations(to_data(element))
    return hashlib.sha256(canonical_json(data)).hexdigest()


# trace: PRD-TRACE-015, PRD-CORE-028
def element_hashes(ir: Ir) -> dict[str, str]:
    """Give the hash of each element of the IR, in the order of the identities."""
    hashes = {element.identity: element_hash(element) for element in ir.elements}
    return dict(sorted(hashes.items()))


def _without_locations(data: JsonValue) -> JsonValue:
    """Remove each source location from JSON data of the IR.

    In the IR, only `Location` objects have the key "location".
    """
    match data:
        case dict():
            return {
                key: _without_locations(value)
                for key, value in data.items()
                if key != _LOCATION_KEY
            }
        case list():
            return [_without_locations(item) for item in data]
        case _:
            return data
