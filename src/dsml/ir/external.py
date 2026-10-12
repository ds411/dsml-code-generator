# trace: PRD-CORE-055, PRD-CORE-026
"""Find the IR elements that the OpenAPI file of an external API gives.

The IR adapter converts the OpenAPI file of each `ExternalApi` element into
`Entity`, `Field`, `Relation`, `Operation` and `Parameter` elements
(`dsml.adapter.openapi`). The owner of each schema and operation is the
external API. The rules for the entities and operations of the model, for
example the `#Key` field of STR-006, do not apply to these elements. This
module does not import OpenSysML.
"""

from dsml.ir.model import Ir


# trace: PRD-CORE-055
def imported(ir: Ir) -> frozenset[str]:
    """Give the identities of the elements that the OpenAPI file of an external API gives."""
    owners = {item.identity: item.owner for item in ir.elements}
    apis = {item.identity for item in ir.elements if item.kind == "ExternalApi"}
    found: set[str] = set()
    for element in ir.elements:
        owner = element.owner
        seen: set[str] = set()
        while owner is not None and owner not in seen:
            if owner in apis:
                found.add(element.identity)
                break
            seen.add(owner)
            owner = owners.get(owner)
    return frozenset(found)
