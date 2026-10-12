"""Tests of the React client of an imported OpenAPI file (story #175).

A `react` application can call an external API in place of an application
of the model (PRD-APP-006). The IR adapter converts the OpenAPI file into IR
entities and operations (story #163). The entities layer and the features
layer write the client from these IR elements.

The test model `tests/models/react/external-api/external-api.sysml` calls
the OpenAPI file `pet-store.openapi.json` in the same folder. The golden
files in `tests/golden/react/external-api/` are the full project of the
application `petPortal`. Write them again with
`uv run python scripts/write_golden_react.py`. The CI job "React golden
project" runs Prettier, `tsc`, ESLint and Steiger on the golden project.
"""

import dataclasses
import json
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import pytest

from dsml.adapter.convert import make_ir
from dsml.config import Configuration, parse_configuration
from dsml.errors import ToolchainError
from dsml.generate.generators import collect
from dsml.generate.react import ReactGenerator
from dsml.generate.react_common import ReactContext
from dsml.generate.react_entities import entities_files, external_entity_slices
from dsml.generate.react_external import external_apis
from dsml.generate.react_features import feature_slices, features_files
from dsml.generate.templates import TemplateEngine
from dsml.generate.trace import SymbolKind
from dsml.generate.writer import OutputFile, application_part
from dsml.ir.model import Element, Ir, Link, Location

ROOT = Path(__file__).resolve().parent.parent
MODEL_FOLDER = ROOT / "tests" / "models" / "react" / "external-api"
MODEL = MODEL_FOLDER / "external-api.sysml"
OPENAPI = MODEL_FOLDER / "pet-store.openapi.json"
GOLDEN = ROOT / "tests" / "golden" / "react" / "external-api"
CONFIGURATION = '[applications.petPortal]\noutput = "."\n'
LOCATION = Location(file="model.sysml", line=1, column=1)
TEMPORARY_MODEL = """\
package PetPortal {
    private import DSML::*;

    #Application part petPortal { :>> target = Target::react; }

    #ExternalApi part petStore { :>> openApiFile = "pet-store.openapi.json"; }

    #Calls dependency from petPortal to petStore;
}
"""
"""A copy of the test model that reads the OpenAPI file from the root of a test folder."""


def configuration() -> Configuration:
    return parse_configuration(f"schema = 1\n\n{CONFIGURATION}", Path("dsml.toml"))


@pytest.fixture(scope="module")
def pet_ir() -> Ir:
    return make_ir([MODEL], ROOT)


def portal(ir: Ir) -> Element:
    return next(item for item in ir.elements if item.name == "petPortal")


def context(ir: Ir) -> ReactContext:
    item = portal(ir)
    return ReactContext(
        TemplateEngine(), ir, item, configuration(), "", application_part(item.name)
    )


def text(files: Iterable[OutputFile], path: str) -> str:
    return next(file for file in files if file.path == path).content.decode()


def golden_files() -> dict[str, bytes]:
    return {
        path.relative_to(GOLDEN).as_posix(): path.read_bytes()
        for path in sorted(GOLDEN.rglob("*"))
        if path.is_file()
    }


def changed_ir(tmp_path: Path, change: Callable[[Any], None]) -> Ir:
    """Make the IR of the test model with a changed copy of the OpenAPI file.

    `change` is a function that gets the OpenAPI document and changes it.
    """
    document = json.loads(OPENAPI.read_text(encoding="utf-8"))
    change(document)
    (tmp_path / "pet-store.openapi.json").write_text(json.dumps(document), encoding="utf-8")
    model = tmp_path / "model.sysml"
    model.write_text(TEMPORARY_MODEL, encoding="utf-8")
    ir = make_ir([model], tmp_path)
    assert not ir.findings, ir.findings
    return ir


# trace: PRD-CORE-030, PRD-APP-006
def test_output_of_the_external_api_model_agrees_with_the_golden_files(pet_ir: Ir) -> None:
    files = collect([ReactGenerator()], pet_ir, configuration(), None)
    output = {file.path: file.content for file in files}
    assert output == golden_files(), (
        "The output is different from the golden files. If the change is correct, run "
        "uv run python scripts/write_golden_react.py and examine the differences."
    )


# trace: PRD-APP-006, PRD-APP-210
def test_each_schema_of_a_response_gives_one_entity_slice(pet_ir: Ir) -> None:
    entities = external_entity_slices(pet_ir, portal(pet_ir))
    assert [(item.slice, [query.name for query in item.queries]) for item in entities] == [
        ("owner", ["readOwner"]),
        ("pet", ["readPet"]),
        ("pet-page", ["listPets"]),
        ("tag", ["listTags"]),
    ]
    # The schemas of a request body (NewPet, PetName) give no entity slice.
    pet_page = next(item for item in entities if item.slice == "pet-page")
    assert [item.name for item in pet_page.schemas] == ["Owner", "Tag", "Pet", "PetPage"]


# trace: PRD-APP-006, PRD-APP-224
def test_query_keys_and_query_options_of_the_operations_with_get(pet_ir: Ir) -> None:
    files = entities_files(context(pet_ir))
    page = text(files, "src/entities/pet-page/api/pet-page-queries.gen.ts")
    assert 'export const petPageQueryKey = ["pet-page"] as const;' in page
    assert 'return ["pet-page", "listPets", parameters] as const;' in page
    # Each parameter of listPets is optional, thus the parameters have a default.
    assert "export function listPetsQueryOptions(parameters: ListPetsParameters = {})" in page
    assert '  status?: "available" | "sold";' in page
    assert "...(parameters.limit == null ? {} : { limit: parameters.limit })," in page
    owner = text(files, "src/entities/owner/api/owner-queries.gen.ts")
    assert "path: `/owners/${encodeURIComponent(String(parameters.ownerId))}`," in owner
    tags = text(files, "src/entities/tag/api/tag-queries.gen.ts")
    assert "export function listTagsQueryKey() {" in tags
    assert "return z.array(tagSchema).parse(body);" in tags


# trace: PRD-APP-006, PRD-APP-211
def test_model_file_has_the_schemas_that_the_schema_refers_to(pet_ir: Ir) -> None:
    model = text(entities_files(context(pet_ir)), "src/entities/pet/model/pet.gen.ts")
    assert "const ownerSchema = z.object({" in model
    assert "const tagSchema = z.object({" in model
    assert "export const petSchema = z.object({" in model
    assert "  owner: ownerSchema.nullable().optional()," in model
    assert "  tags: z.array(tagSchema)," in model
    assert "  createdAt: z.iso.datetime({ offset: true, local: true })," in model
    assert model.index("const ownerSchema") < model.index("export const petSchema")


# trace: PRD-APP-006, PRD-APP-210, PRD-APP-225
def test_each_operation_with_a_change_gives_one_feature_slice(pet_ir: Ir) -> None:
    features = feature_slices(pet_ir, portal(pet_ir))
    assert [(item.slice, item.method, item.output_type) for item in features] == [
        ("create-pet", "post", "CreatePetOutput"),
        ("delete-pet", "delete", "void"),
        ("rename-pet", "patch", "RenamePetOutput"),
    ]
    # The mutation invalidates the queries of each entity slice of the external API.
    assert all(
        [entity.slice for entity in item.changed] == ["owner", "pet", "pet-page", "tag"]
        for item in features
    )


# trace: PRD-APP-006, PRD-APP-226
def test_mutation_sends_the_path_the_query_and_the_body(pet_ir: Ir) -> None:
    files = features_files(context(pet_ir))
    rename = text(files, "src/features/rename-pet/api/rename-pet.gen.ts")
    assert "export const renamePetInputSchema = z.strictObject({" in rename
    assert "path: `/pets/${encodeURIComponent(data.petId)}`," in rename
    assert "...(data.notify == null ? {} : { notify: data.notify })," in rename
    assert "    body: {\n      name: data.name,\n    }," in rename
    assert "export const renamePetOutputSchema = petSchema;" in rename
    assert 'import { petQueryKey, petSchema } from "@/entities/pet";' in rename
    create = text(files, "src/features/create-pet/api/create-pet.gen.ts")
    assert "  price: decimalValue()," in create
    assert "  nicknames: z.array(z.string())," in create
    assert "query:" not in create
    delete = text(files, "src/features/delete-pet/api/delete-pet.gen.ts")
    assert "body" not in delete.split("export async function deletePet")[1].split("}\n")[0]
    form = text(files, "src/features/create-pet/ui/create-pet-form.gen.tsx")
    assert '<form.Field name="birthDate">' in form
    assert "Birth date" in form


# trace: PRD-APP-017, PRD-TRACE-005, PRD-TRACE-006
def test_external_files_have_the_header_and_symbols(pet_ir: Ir) -> None:
    files = entities_files(context(pet_ir))
    model = next(file for file in files if file.path == "src/entities/tag/model/tag.gen.ts")
    elements = ("PetPortal::petStore::Tag", "PetPortal::petStore::listTags")
    assert model.content.decode().splitlines()[1] == f"// Elements: {', '.join(elements)}"
    assert [(symbol.kind, symbol.name) for symbol in model.symbols] == [
        (SymbolKind.CLASS, "tagSchema"),
        (SymbolKind.CLASS, "Tag"),
    ]
    api = next(
        file
        for file in features_files(context(pet_ir))
        if file.path == "src/features/delete-pet/api/delete-pet.gen.ts"
    )
    assert api.content.decode().splitlines()[1] == ("// Elements: PetPortal::petStore::deletePet")


def test_application_with_no_view_has_a_typed_empty_navigation(pet_ir: Ir) -> None:
    files = collect([ReactGenerator()], pet_ir, configuration(), None)
    views = text(list(files), "src/app/router/views.gen.ts")
    assert "export const NAVIGATION: readonly View[] = [];" in views


def test_external_api_with_no_calls_gives_no_slices(pet_ir: Ir) -> None:
    links = tuple(item for item in pet_ir.links if item.type != "calls")
    ir = dataclasses.replace(pet_ir, links=links)
    assert external_apis(ir, portal(ir)) == []
    assert external_entity_slices(ir, portal(ir)) == []
    assert feature_slices(ir, portal(ir)) == []


def test_get_with_no_response_gives_an_error(tmp_path: Path) -> None:
    def change(document: Any) -> None:
        document["paths"]["/tags"]["get"]["responses"] = {"204": {"description": "None."}}

    ir = changed_ir(tmp_path, change)
    with pytest.raises(ToolchainError, match=r"listTags .* method GET and has no JSON response"):
        external_entity_slices(ir, portal(ir))


def test_object_property_in_a_request_body_gives_an_error(tmp_path: Path) -> None:
    def change(document: Any) -> None:
        properties = document["components"]["schemas"]["PetName"]["properties"]
        properties["tag"] = {"$ref": "#/components/schemas/Tag"}

    ir = changed_ir(tmp_path, change)
    with pytest.raises(ToolchainError, match=r"property tag .* refers to an object schema"):
        feature_slices(ir, portal(ir))


def test_array_of_numbers_in_a_request_body_gives_an_error(tmp_path: Path) -> None:
    def change(document: Any) -> None:
        properties = document["components"]["schemas"]["PetName"]["properties"]
        properties["scores"] = {"type": "array", "items": {"type": "integer"}}

    ir = changed_ir(tmp_path, change)
    with pytest.raises(ToolchainError, match="array of the type Integer"):
        feature_slices(ir, portal(ir))


def test_parameter_and_body_property_with_one_name_give_an_error(tmp_path: Path) -> None:
    def change(document: Any) -> None:
        properties = document["components"]["schemas"]["PetName"]["properties"]
        properties["petId"] = {"type": "string"}

    ir = changed_ir(tmp_path, change)
    with pytest.raises(ToolchainError, match='with the name "petId"'):
        feature_slices(ir, portal(ir))


def test_recursive_schema_gives_an_error(tmp_path: Path) -> None:
    def change(document: Any) -> None:
        properties = document["components"]["schemas"]["Tag"]["properties"]
        properties["parent"] = {"anyOf": [{"$ref": "#/components/schemas/Tag"}, {"type": "null"}]}

    ir = changed_ir(tmp_path, change)
    with pytest.raises(ToolchainError, match=r"schema Tag .* refers to itself"):
        entities_files(context(ir))


def test_application_and_external_api_with_one_slice_name_give_an_error(pet_ir: Ir) -> None:
    order = make_ir(
        [ROOT / "docs" / "model" / "examples" / "order-portal" / "order-portal.sysml"], ROOT
    )
    api = next(
        item for item in order.elements if item.kind == "Application" and item.name == "orderApi"
    )
    # The order API exposes the entity Order. The schema "Order" of the external API
    # has the same slice name.
    elements = tuple(
        dataclasses.replace(item, name="Order")
        if item.identity == "PetPortal::petStore::Pet"
        else item
        for item in pet_ir.elements
    )
    link = Link(type="calls", source="PetPortal::petPortal", target=api.identity, location=LOCATION)
    ir = dataclasses.replace(
        pet_ir,
        elements=(*elements, *order.elements),
        links=(*pet_ir.links, *order.links, link),
    )
    with pytest.raises(ToolchainError, match='entity slice "order"'):
        entities_files(context(ir))


def test_name_that_is_not_an_identifier_gives_an_error(tmp_path: Path) -> None:
    def change(document: Any) -> None:
        properties = document["components"]["schemas"]["PetName"]["properties"]
        properties["first-name"] = {"type": "string"}

    ir = changed_ir(tmp_path, change)
    with pytest.raises(ToolchainError, match=r'"first-name" .* not a TypeScript identifier'):
        external_apis(ir, portal(ir))
