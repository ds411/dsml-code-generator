"""Tests of the DSML library package (story #13).

These tests start a private `sysml-grpc` child process. If the binary is not
in the cache, the `opensysml` client downloads it one time.
"""

import re
import shutil
import subprocess
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from dsml.adapter.engine import Engine, ParsedModel
from dsml.library import LIBRARY_FILE, LIBRARY_VERSION, library_document, library_text

ROOT = Path(__file__).resolve().parent.parent
MODELS = Path(__file__).resolve().parent / "models" / "dsml"

SEMANTIC_METADATA = "Metaobjects::SemanticMetadata"

# The keywords of element kinds in the scope of story #13. Each one
# specializes Metaobjects::SemanticMetadata (PRD-DSML-009).
ELEMENT_KIND_KEYWORDS = {
    "Application",
    "AwsCognito",
    "AwsEcsService",
    "AwsRdsPostgres",
    "AwsSecrets",
    "AwsVpc",
    "ContainerService",
    "Entity",
    "Environment",
    "Exposed",
    "Key",
    "Need",
    "Network",
    "Operation",
    "Override",
    "RelationalDatabase",
    "Requirement",
    "Roles",
    "SecretStore",
    "Stakeholder",
    "ToolingAccount",
    "UserDirectory",
    "Verification",
}

# Keywords for a dependency, and metadata that holds its own attributes.
# OpenSysML 0.9.2 does not accept semantic metadata on a dependency.
PLAIN_KEYWORDS = {
    "Calls",
    "Destructive",
    "DsmlVersion",
    "FieldRules",
    "Realizes",
    "Uses",
    "Waiver",
}

ENUMERATIONS = {
    "CrudKind": ("create", "read", "update", "delete", "list"),
    "HttpMethod": ("get", "post", "put", "patch", "delete"),
    "Priority": ("must", "should", "could", "wont"),
    "RequirementKind": ("functional", "performance", "security", "interface", "constraint"),
    "Status": ("draft", "approved", "implemented", "verified", "retired"),
    "Target": ("fastapi", "react", "nextjs"),
    "VerificationMethod": ("test", "analysis", "inspection", "demonstration"),
}


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    with Engine() as started:
        yield started


@pytest.fixture(scope="module")
def library(engine: Engine) -> ParsedModel:
    return engine.parse_texts([library_document()])


@pytest.fixture(scope="module")
def keywords_model(engine: Engine) -> ParsedModel:
    return _parse_with_library(engine, "keywords.sysml")


def _parse_with_library(engine: Engine, name: str) -> ParsedModel:
    model_file = MODELS / name
    return engine.parse_texts(
        [library_document(), (model_file.name, model_file.read_text(encoding="utf-8"))]
    )


# trace: PRD-DSML-001, PRD-DSML-004
def test_library_parses_and_resolves(library: ParsedModel) -> None:
    assert library.diagnostics == ()
    assert library.ok


# trace: PRD-DSML-001
def test_library_is_the_package_dsml() -> None:
    assert re.search(r"^library package DSML \{$", library_text(), re.MULTILINE)


# trace: PRD-DSML-003, PRD-DSML-009
def test_library_has_each_keyword(library: ParsedModel) -> None:
    keywords = library.owned_elements("DSML", kinds={"MetadataDefinition"})
    assert {item.name for item in keywords} == ELEMENT_KIND_KEYWORDS | PLAIN_KEYWORDS


# trace: PRD-DSML-009
def test_element_kind_keywords_are_semantic_metadata(library: ParsedModel) -> None:
    keywords = library.owned_elements("DSML", kinds={"MetadataDefinition"})
    semantic = {item.name for item in keywords if SEMANTIC_METADATA in item.general}
    assert semantic == ELEMENT_KIND_KEYWORDS


# trace: PRD-DSML-016, PRD-DSML-020, PRD-DSML-027, PRD-DSML-029, PRD-DSML-046
def test_library_has_each_enumeration(library: ParsedModel) -> None:
    enumerations = library.owned_elements("DSML", kinds={"EnumerationDefinition"})
    assert {item.name for item in enumerations} == set(ENUMERATIONS)
    for name, literals in ENUMERATIONS.items():
        items = library.owned_elements(f"DSML::{name}", kinds={"EnumerationUsage"})
        assert {item.name for item in items} == set(literals), name


# trace: PRD-DSML-023
def test_library_has_each_attribute_type(library: ParsedModel) -> None:
    attribute_types = library.owned_elements("DSML", kinds={"AttributeDefinition"})
    general = {item.name: item.general for item in attribute_types}
    assert general["Decimal"] == ("ScalarValues::Real",)
    assert general["Date"] == ("ScalarValues::String",)
    assert general["DateTime"] == ("ScalarValues::String",)
    assert general["Uuid"] == ("ScalarValues::String",)


# trace: PRD-DSML-056
def test_library_version_agrees_with_the_source() -> None:
    match = re.search(
        r"@DsmlVersion \{ major = (\d+); minor = (\d+); patch = (\d+); \}", library_text()
    )
    assert match is not None
    assert ".".join(match.groups()) == LIBRARY_VERSION == "1.0.0"


# trace: PRD-CORE-033
def test_library_document_name_is_relative() -> None:
    name, _ = library_document()
    assert name == f"dsml/{LIBRARY_FILE}"


# trace: PRD-DSML-003, PRD-DSML-004
def test_model_with_each_keyword_parses_and_resolves(keywords_model: ParsedModel) -> None:
    assert keywords_model.diagnostics == ()


# trace: PRD-DSML-003, PRD-DSML-009
@pytest.mark.parametrize(
    ("element", "keyword"),
    [
        ("trackOrders", "Need"),
        ("getOrder", "Requirement"),
        ("orderApi", "Application"),
        ("network", "Network"),
        ("apiService", "ContainerService"),
        ("orderDb", "RelationalDatabase"),
        ("users", "UserDirectory"),
        ("secrets", "SecretStore"),
        ("networkAws", "AwsVpc"),
        ("apiServiceAws", "AwsEcsService"),
        ("orderDbAws", "AwsRdsPostgres"),
        ("usersAws", "AwsCognito"),
        ("secretsAws", "AwsSecrets"),
        ("prod", "Environment"),
        ("tooling", "ToolingAccount"),
    ],
)
def test_keyword_gives_the_base_type(
    keywords_model: ParsedModel, element: str, keyword: str
) -> None:
    assert keywords_model.has_metadata(element, f"DSML::{keyword}", "Keywords")
    assert keywords_model.is_type(element, f"DSML::BaseTypes::{keyword}", "Keywords")


# trace: PRD-DSML-009, PRD-DSML-011, PRD-DSML-022, PRD-DSML-028
@pytest.mark.parametrize(
    ("element", "keyword"),
    [
        ("owner", "Stakeholder"),
        ("orderApi::orders", "Entity"),
        ("orderApi::cancelOrder", "Operation"),
    ],
)
def test_keyword_on_a_definition_gives_the_base_type(
    keywords_model: ParsedModel, element: str, keyword: str
) -> None:
    assert keywords_model.is_type(element, f"DSML::BaseTypes::{keyword}", "Keywords")


# trace: PRD-DSML-010, PRD-DSML-027, PRD-DSML-042
def test_keyword_on_a_typed_usage_gives_the_base_type_features(
    keywords_model: ParsedModel,
) -> None:
    namespace = "Keywords"
    assert keywords_model.has_metadata("orderApi::orders", "DSML::Exposed", namespace)
    assert keywords_model.has_metadata("prod::orderDbProd", "DSML::Override", namespace)
    assert keywords_model.evaluate_bool("orderApi.cancelOrder.'public' == false", namespace)
    assert keywords_model.evaluate_bool("prod.orderDbProd.multiAz == true", namespace)
    assert keywords_model.evaluate_bool("orderDbAws.multiAz == false", namespace)


def test_typed_usage_is_not_an_instance_of_the_keyword_base_type(
    keywords_model: ParsedModel,
) -> None:
    """A known limit of OpenSysML 0.9.2. See docs/notes/dsml-library.md.

    A usage with a declared type and a keyword gets the features of the
    base type, but "istype" does not give true for the base type. Thus the
    IR adapter must find the keyword with "@", not with "istype". If a new
    OpenSysML version removes the limit, this test fails.
    """
    assert not keywords_model.is_type(
        "orderApi::cancelOrder", "DSML::BaseTypes::Exposed", "Keywords"
    )


# trace: PRD-DSML-009
def test_attribute_that_the_base_type_does_not_have_gives_an_error(engine: Engine) -> None:
    model = _parse_with_library(engine, "unknown-attribute.sysml")
    assert [(item.file, item.line, item.code, item.message) for item in model.diagnostics] == [
        ("unknown-attribute.sysml", 6, "unresolved", "unresolved reference: colour")
    ]


# trace: PRD-DSML-006, PRD-CORE-048
def test_wheel_contains_the_library(tmp_path: Path) -> None:
    uv = shutil.which("uv")
    assert uv is not None, "The test must have uv to build the wheel."
    subprocess.run(
        [uv, "build", "--wheel", "--out-dir", str(tmp_path), "--quiet"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    (wheel,) = tmp_path.glob("dsml-*.whl")
    with zipfile.ZipFile(wheel) as archive:
        packaged = archive.read(f"dsml/library/{LIBRARY_FILE}").decode("utf-8")
    assert packaged == library_text()
