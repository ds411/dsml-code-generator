"""Tests of the features layer of the React generator (story #172).

The golden files in `tests/golden/react/order-portal/src/features/` are the
feature slices of the order portal model. Write them again with
`uv run python scripts/write_golden_react.py`.

The Vitest file `tests/react/features/features.test.tsx` renders the forms
of the golden project in the CI job "React golden project". It examines the
field errors, the problem details errors, the keyboard access and the
invalidation of the entity queries after a mutation.
"""

import dataclasses
from pathlib import Path

import pytest

from dsml.adapter.convert import make_ir
from dsml.config import Configuration, parse_configuration
from dsml.errors import ToolchainError
from dsml.generate import react_features
from dsml.generate.fastapi_operations import CustomSlice
from dsml.generate.generators import collect
from dsml.generate.react import ReactGenerator
from dsml.generate.react_common import ReactContext
from dsml.generate.react_features import (
    feature_slices,
    features_files,
    import_lines,
    jsx_text_lines,
    signature_lines,
)
from dsml.generate.templates import TemplateEngine
from dsml.generate.trace import SymbolKind
from dsml.generate.writer import Kind, application_part
from dsml.ir.model import Attribute, Element, EnumValue, Ir, Link, Location

ROOT = Path(__file__).resolve().parent.parent
PORTAL_MODEL = ROOT / "docs" / "model" / "examples" / "order-portal" / "order-portal.sysml"
SHOP_MODEL = ROOT / "tests" / "models" / "fastapi" / "shop.sysml"
GOLDEN = ROOT / "tests" / "golden" / "react" / "order-portal"
FEATURES = "src/features/"
CONFIGURATION = '[applications.orderPortal]\noutput = "."\n'
LOCATION = Location(file="model.sysml", line=1, column=1)


def configuration(text: str = CONFIGURATION) -> Configuration:
    return parse_configuration(f"schema = 1\n\n{text}", Path("dsml.toml"))


def react_application(identity: str) -> Element:
    name = identity.rpartition("::")[2]
    return Element(
        identity=identity,
        kind="Application",
        name=name,
        qualified_name=identity,
        location=LOCATION,
        attributes=(Attribute("target", EnumValue("DSML::Target", "react"), LOCATION),),
    )


def with_portal(ir: Ir) -> Ir:
    """Add a React application `shopPortal` that calls `shopApi`."""
    api = next(item for item in ir.elements if item.name == "shopApi")
    portal = react_application("Shop::shopPortal")
    link = Link(type="calls", source=portal.identity, target=api.identity, location=LOCATION)
    return dataclasses.replace(ir, elements=(*ir.elements, portal), links=(*ir.links, link))


@pytest.fixture(scope="module")
def portal_ir() -> Ir:
    return make_ir([PORTAL_MODEL], ROOT)


@pytest.fixture(scope="module")
def shop_ir() -> Ir:
    """The shop model with a React application `shopPortal` that calls `shopApi`."""
    return with_portal(make_ir([SHOP_MODEL], ROOT))


def application(ir: Ir, name: str) -> Element:
    return next(item for item in ir.elements if item.kind == "Application" and item.name == name)


def context(ir: Ir, name: str) -> ReactContext:
    item = application(ir, name)
    return ReactContext(
        TemplateEngine(), ir, item, configuration(), "", application_part(item.name)
    )


def feature_files(files: dict[str, bytes]) -> dict[str, bytes]:
    return {path: content for path, content in files.items() if path.startswith(FEATURES)}


def golden_files() -> dict[str, bytes]:
    return {
        path.relative_to(GOLDEN).as_posix(): path.read_bytes()
        for path in sorted(GOLDEN.rglob("*"))
        if path.is_file()
    }


def shop_text(ir: Ir, path: str) -> str:
    files = {file.path: file for file in features_files(context(ir, "shopPortal"))}
    return files[path].content.decode()


def with_method(ir: Ir, operation: str, method: str) -> Ir:
    """Change the HTTP method of an operation definition."""
    elements = tuple(
        dataclasses.replace(
            item,
            attributes=tuple(
                Attribute("method", EnumValue("DSML::HttpMethod", method), LOCATION)
                if attribute.name == "method"
                else attribute
                for attribute in item.attributes
            ),
        )
        if item.kind == "Operation" and item.name == operation
        else item
        for item in ir.elements
    )
    return dataclasses.replace(ir, elements=elements)


# trace: PRD-CORE-030, PRD-APP-210
def test_feature_files_of_the_order_portal_agree_with_the_golden_files(portal_ir: Ir) -> None:
    files = collect([ReactGenerator()], portal_ir, configuration(), None)
    output = feature_files({file.path: file.content for file in files})
    assert output == feature_files(golden_files()), (
        "The output is different from the golden files. If the change is correct, run "
        "uv run python scripts/write_golden_react.py and examine the differences."
    )
    assert sorted(output) == [
        f"src/features/{name}/{module}"
        for name in ("cancel-order", "create-order", "place-order")
        for module in (f"api/{name}.gen.ts", "index.gen.ts", "index.ts", f"ui/{name}-form.gen.tsx")
    ]


# trace: PRD-APP-204, PRD-CORE-044
def test_public_api_of_a_feature_slice(portal_ir: Ir) -> None:
    files = {file.path: file for file in features_files(context(portal_ir, "orderPortal"))}
    assert files["src/features/place-order/index.ts"].kind is Kind.CREATE_ONCE
    generated = files["src/features/place-order/index.gen.ts"]
    assert generated.kind is Kind.GENERATED
    assert generated.content.decode().splitlines() == [
        "// Generated by dsml 0. Do not edit.",
        "// Elements: OrderPortal::Order, OrderPortal::PlaceOrder, "
        "OrderPortal::orderApi::placeOrder",
        'export * from "./api/place-order.gen";',
        'export * from "./ui/place-order-form.gen";',
    ]


# trace: PRD-APP-206, PRD-APP-210
def test_each_operation_with_a_change_gives_one_slice(shop_ir: Ir) -> None:
    found = {
        item.slice: (item.kind, item.ui_module)
        for item in feature_slices(shop_ir, application(shop_ir, "shopPortal"))
    }
    # The operations read and list and the custom operations with the method
    # GET (findProducts, countCustomers) do not change data.
    assert found == {
        "archive-supplier": ("custom", "ui/archive-supplier-form.gen"),
        "create-customer": ("create", "ui/create-customer-form.gen"),
        "create-product": ("create", "ui/create-product-form.gen"),
        "create-supplier": ("create", "ui/create-supplier-form.gen"),
        "delete-customer": ("delete", "ui/delete-customer-button.gen"),
        "delete-product": ("delete", "ui/delete-product-button.gen"),
        "restock-product": ("custom", "ui/restock-product-form.gen"),
        "update-customer": ("update", "ui/update-customer-form.gen"),
        "update-product": ("update", "ui/update-product-form.gen"),
    }


# trace: PRD-APP-225
def test_mutation_invalidates_the_queries_of_the_changed_entity(shop_ir: Ir) -> None:
    for path, key in (
        ("src/features/create-customer/api/create-customer.gen.ts", "customerQueryKey"),
        ("src/features/delete-product/api/delete-product.gen.ts", "productQueryKey"),
        ("src/features/archive-supplier/api/archive-supplier.gen.ts", "supplierQueryKey"),
    ):
        text = shop_text(shop_ir, path)
        assert "const queryClient = useQueryClient();" in text, path
        assert f"await queryClient.invalidateQueries({{ queryKey: {key} }});" in text, path
        assert "    onSuccess: async () => {" in text, path


# trace: PRD-APP-226
def test_forms_use_tanstack_form_with_the_zod_schema(portal_ir: Ir) -> None:
    text = (GOLDEN / "src/features/create-order/ui/create-order-form.gen.tsx").read_text()
    assert 'import { useForm } from "@tanstack/react-form";' in text
    assert "      onSubmit: createOrderInputSchema,\n" in text
    for name, label in (("note", "Note"), ("status", "Status"), ("total", "Total")):
        assert f'<form.Field name="{name}">' in text
        assert f"<FieldLabel htmlFor={{`${{formId}}-${{field.name}}`}}>{label}" in text.replace(
            "\n                ", ""
        )
    assert text.count("<FieldError errors={shownErrors(field.state.meta)} />") == 3
    custom = (GOLDEN / "src/features/place-order/api/place-order.gen.ts").read_text()
    assert (
        "export const placeOrderInputSchema = z.strictObject({\n  total: decimalValue(),\n});"
        in (custom)
    )


# trace: PRD-APP-227
def test_forms_show_the_title_and_the_detail_of_a_problem(shop_ir: Ir) -> None:
    for path in (
        "src/features/update-product/ui/update-product-form.gen.tsx",
        "src/features/delete-product/ui/delete-product-button.gen.tsx",
    ):
        text = shop_text(shop_ir, path)
        assert "const title = error instanceof ApiError ? error.title : error.message;" in text
        assert "<AlertDescription>{detail}</AlertDescription>" in text
        assert "<OperationError error={mutation.error} />" in text


# trace: PRD-APP-210, PRD-APP-228
def test_delete_button_has_a_confirmation_dialog(shop_ir: Ir) -> None:
    text = shop_text(shop_ir, "src/features/delete-customer/ui/delete-customer-button.gen.tsx")
    assert "export function DeleteCustomerButton({" in text
    assert "  id: number;" in text
    for tag in ("AlertDialogTrigger asChild", "AlertDialogCancel", "AlertDialogAction"):
        assert f"<{tag}>" in text or f"<{tag}" in text
    assert "<AlertDialogTitle>Delete this Customer</AlertDialogTitle>" in text
    assert "mutation.mutate(id, {" in text
    api = shop_text(shop_ir, "src/features/delete-customer/api/delete-customer.gen.ts")
    assert "export async function deleteCustomer(id: number): Promise<void> {" in api
    assert "path: `/customers/${encodeURIComponent(String(id))}`," in api


# trace: PRD-APP-210, PRD-APP-226
def test_update_form_gets_the_key_and_sends_the_update_input(shop_ir: Ir) -> None:
    api = shop_text(shop_ir, "src/features/update-product/api/update-product.gen.ts")
    assert (
        "export interface UpdateProductVariables {\n  id: string;\n  input: UpdateProductInput;\n}"
        in (api)
    )
    assert 'method: "PATCH",' in api
    assert "body: updateProductInputSchema.parse(variables.input)," in api
    form = shop_text(shop_ir, "src/features/update-product/ui/update-product-form.gen.tsx")
    assert "const initialValues: UpdateProductInput = {};" in form
    assert "{ id, input: value }," in form
    # Each field of the update input is optional.
    assert 'value={field.state.value ?? ""}' in form
    assert "value={Number.isNaN(field.state.value)" not in form


# trace: PRD-APP-226, PRD-APP-228
def test_controls_follow_the_field_types(shop_ir: Ir) -> None:
    form = shop_text(shop_ir, "src/features/create-product/ui/create-product-form.gen.tsx")
    assert 'type="number"\n                step="1"' in form
    assert 'type="number"\n                step="any"' in form
    assert 'type="datetime-local"' in form
    assert 'inputMode="decimal"' in form
    assert '<NativeSelectOption value="book">book</NativeSelectOption>' in form
    assert "field.handleChange(value as typeof field.state.value);" in form
    assert "stock: Number.NaN," in form
    customer = shop_text(shop_ir, "src/features/create-customer/ui/create-customer-form.gen.tsx")
    assert 'type="checkbox"' in customer
    assert "field.handleChange(event.target.checked);" in customer
    assert 'type="date"' in customer
    assert "vip: false," in customer


def test_list_parameter_of_a_custom_operation_uses_a_text_area(shop_ir: Ir) -> None:
    ir = with_method(shop_ir, "FindProducts", "post")
    api = shop_text(ir, "src/features/find-products/api/find-products.gen.ts")
    assert "codes: z.array(z.string()).optional()," in api
    assert "const findProductsItemSchema = z.object({" in api
    assert "export const findProductsOutputSchema = z.array(findProductsItemSchema);" in api
    form = shop_text(ir, "src/features/find-products/ui/find-products-form.gen.tsx")
    assert 'value={(field.state.value ?? []).join("\\n")}' in form
    assert "field.handleChange(textLines(event.target.value));" in form


def test_list_parameter_of_a_number_type_gives_an_error(shop_ir: Ir) -> None:
    ir = with_method(shop_ir, "FindProducts", "post")
    elements = tuple(
        dataclasses.replace(item, types=tuple(t.replace("String", "Integer") for t in item.types))
        if item.identity == "Shop::FindProducts::codes"
        else item
        for item in ir.elements
    )
    ir = dataclasses.replace(ir, elements=elements)
    with pytest.raises(ToolchainError, match="has no form control for this list"):
        feature_slices(ir, application(ir, "shopPortal"))


def test_two_operations_with_one_slice_name_give_an_error(
    shop_ir: Ir, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = react_features.custom_slices

    def twice(*arguments: object) -> list[CustomSlice]:
        found = original(*arguments)  # type: ignore[arg-type]
        return [*found, *found]

    monkeypatch.setattr(react_features, "custom_slices", twice)
    with pytest.raises(ToolchainError, match='feature slice name "restock-product"'):
        feature_slices(shop_ir, application(shop_ir, "shopPortal"))


# trace: PRD-APP-203
def test_feature_files_import_only_lower_layers_through_a_public_api(shop_ir: Ir) -> None:
    for file in features_files(context(shop_ir, "shopPortal")):
        text = file.content.decode()
        for line in text.splitlines():
            if not line.startswith("} from ") and not line.startswith("import "):
                continue
            source = line.rsplit(" from ", 1)[-1].strip('";')
            if source.startswith("@/"):
                layer, _, rest = source[2:].partition("/")
                assert layer in ("entities", "shared"), (file.path, source)
                assert "/" not in rest, (file.path, source)
            elif source.startswith("."):
                assert source.startswith("../api/"), (file.path, source)


# trace: PRD-APP-017, PRD-TRACE-005, PRD-TRACE-006
def test_feature_files_have_the_header_and_symbols(portal_ir: Ir) -> None:
    files = {file.path: file for file in features_files(context(portal_ir, "orderPortal"))}
    api = files["src/features/cancel-order/api/cancel-order.gen.ts"]
    elements = (
        "OrderPortal::CancelOrder",
        "OrderPortal::Order",
        "OrderPortal::orderApi::cancelOrder",
    )
    assert api.content.decode().splitlines()[1] == f"// Elements: {', '.join(elements)}"
    assert [(symbol.kind, symbol.name) for symbol in api.symbols] == [
        (SymbolKind.CLASS, "cancelOrderInputSchema"),
        (SymbolKind.CLASS, "CancelOrderInput"),
        (SymbolKind.CLASS, "cancelOrderOutputSchema"),
        (SymbolKind.CLASS, "CancelOrderOutput"),
        (SymbolKind.FUNCTION, "cancelOrder"),
        (SymbolKind.FUNCTION, "useCancelOrderMutation"),
    ]
    assert all(symbol.elements == elements for symbol in api.symbols)
    form = files["src/features/create-order/ui/create-order-form.gen.tsx"]
    assert [symbol.name for symbol in form.symbols] == [
        "CreateOrderFormProps",
        "initialValues",
        "isInvalid",
        "shownErrors",
        "optionalText",
        "OperationError",
        "CreateOrderForm",
    ]
    assert not files["src/features/create-order/index.ts"].symbols


def test_an_application_with_no_called_application_has_no_feature_slices(shop_ir: Ir) -> None:
    alone = react_application("Shop::alonePortal")
    ir = dataclasses.replace(shop_ir, elements=(*shop_ir.elements, alone))
    assert feature_slices(ir, alone) == []


@pytest.mark.parametrize(
    ("opening", "text", "expected"),
    [
        ("<FieldLabel htmlFor={id}>", "Note", ["  <FieldLabel htmlFor={id}>Note</FieldLabel>"]),
        (
            '<Button type="submit" disabled={x}>',
            "Create",
            ['  <Button type="submit" disabled={x}>', "    Create", "  </Button>"],
        ),
        (
            '<NativeSelectOption value="cancelled">',
            "cancelled" * 4,
            [
                '  <NativeSelectOption value="cancelled">',
                f"    {'cancelled' * 4}",
                "  </NativeSelectOption>",
            ],
        ),
    ],
)
def test_jsx_text_lines_follow_prettier(opening: str, text: str, expected: list[str]) -> None:
    assert jsx_text_lines("  ", opening, text) == expected


def test_import_and_signature_lines_follow_prettier() -> None:
    assert import_lines(["a", "b"], "@/x") == ['import { a, b } from "@/x";']
    names = [f"name{index:02d}" for index in range(8)]
    assert import_lines(names, "@/x") == [
        "import {",
        *(f"  {name}," for name in names),
        '} from "@/x";',
    ]
    assert signature_lines("export function a", "b: B", ": C") == ["export function a(b: B): C {"]
    long = "x" * 80
    assert signature_lines("export function a", f"b: {long}", ": C") == [
        "export function a(",
        f"  b: {long},",
        "): C {",
    ]
