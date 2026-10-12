# trace: PRD-CORE-030
"""Write the golden files of the FastAPI generator again.

Story #75 added the golden output of the example model in
tests/golden/fastapi/order-service/. Story #84 added the golden output of
the test model tests/models/fastapi/shop.sysml in tests/golden/fastapi/shop/.
Story #88 added tests/golden/fastapi/handler-check/: the generated files of
the slice cancel_order for a changed example model. The CI job "FastAPI
golden project" uses them to show a type check error in a hand-written
handler that does not agree with the changed model (PRD-CORE-045). Story
#164 added the golden output of the order portal model
docs/model/examples/order-portal/order-portal.sysml in
tests/golden/fastapi/order-portal/. A `react` application calls its FastAPI
application, thus the output has the CORS middleware (PRD-APP-136). The
file handler.py in that folder is hand-written. The script does not change
it. The tests tests/test_fastapi_generator.py and tests/test_fastapi_slices.py
compare the output of the FastAPI generator with these files. The CI job
"FastAPI golden project" runs ruff, pyright and pytest on each golden
project. Run this script from the root of the repository after a change to
the generator or to its templates:

    uv run python scripts/write_golden_fastapi.py

Then examine the differences with `git diff` before you commit them.
"""

import shutil
import sys
from dataclasses import replace
from pathlib import Path

from dsml.adapter.convert import make_ir
from dsml.config import parse_configuration
from dsml.generate.fastapi import FastApiGenerator
from dsml.generate.generators import collect
from dsml.generate.writer import Kind, apply_plan, make_plan
from dsml.ir.model import Element, Ir, StringValue

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_MODEL = ROOT / "docs" / "model" / "examples" / "order-service.sysml"
SHOP_MODEL = ROOT / "tests" / "models" / "fastapi" / "shop.sysml"
PORTAL_MODEL = ROOT / "docs" / "model" / "examples" / "order-portal" / "order-portal.sysml"
GOLDEN = ROOT / "tests" / "golden" / "fastapi" / "order-service"
SHOP_GOLDEN = ROOT / "tests" / "golden" / "fastapi" / "shop"
PORTAL_GOLDEN = ROOT / "tests" / "golden" / "fastapi" / "order-portal"
CONFIGURATION = """\
schema = 1

[model]
paths = ["model"]

[applications.orderApi]
output = "services/order-api"
"""
"""The configuration file of the golden output of the example model."""

SHOP_CONFIGURATION = """\
schema = 1

[model]
paths = ["model"]

[applications.shopApi]
output = "services/shop-api"
"""
"""The configuration file of the golden output of the shop model."""

HANDLER_CHECK = ROOT / "tests" / "golden" / "fastapi" / "handler-check"
"""The generated files of the slice cancel_order for the changed example model."""

HANDLER_CHECK_SLICE = "services/order-api/app/features/order/cancel_order"
"""The folder of the slice cancel_order, relative to the configuration file."""

HANDLER_CHECK_FILES = ("endpoint_gen.py", "schemas_gen.py")
"""The generated files of the slice that the CI job puts into the golden project."""

GOLDENS = (
    (GOLDEN, EXAMPLE_MODEL, CONFIGURATION),
    (SHOP_GOLDEN, SHOP_MODEL, SHOP_CONFIGURATION),
    (PORTAL_GOLDEN, PORTAL_MODEL, CONFIGURATION),
)
"""The golden folder, the model and the configuration file of each golden output."""


def write_output(
    folder: Path, model: Path = EXAMPLE_MODEL, configuration_text: str = CONFIGURATION
) -> None:
    """Write the output of the FastAPI generator for a model into `folder`.

    The folder gets the generated files and the manifests in `.dsml/`, but
    not the configuration file.
    """
    configuration = parse_configuration(configuration_text, folder / "dsml.toml")
    ir = make_ir([model], ROOT)
    files = collect([FastApiGenerator()], ir, configuration, None)
    apply_plan(folder, make_plan(folder, files, None))


# trace: PRD-CORE-045
def changed_example(ir: Ir) -> Ir:
    """Give the IR of the example model with the new name `orderKey` for `orderId`.

    The `in` parameter of the operation CancelOrder and the path parameter
    get the new name. Thus the input schema has the field `order_key` in
    place of `order_id`.
    """
    elements: list[Element] = []
    for element in ir.elements:
        if element.identity == "OrderService::CancelOrder::orderId":
            element = replace(element, name="orderKey")
        elif element.identity == "OrderService::CancelOrder":
            attributes = tuple(
                replace(item, value=StringValue("/orders/{orderKey}/cancel"))
                if item.name == "path"
                else item
                for item in element.attributes
            )
            element = replace(element, attributes=attributes)
        elements.append(element)
    return replace(ir, elements=tuple(elements))


def handler_check_files() -> dict[str, bytes]:
    """Give the generated files of the slice cancel_order of the changed example model."""
    configuration = parse_configuration(CONFIGURATION, ROOT / "dsml.toml")
    ir = changed_example(make_ir([EXAMPLE_MODEL], ROOT))
    files = collect([FastApiGenerator()], ir, configuration, None)
    return {
        file.path.rpartition("/")[2]: file.content
        for file in files
        if file.kind is Kind.GENERATED
        and file.path.rpartition("/")[0] == HANDLER_CHECK_SLICE
        and file.path.rpartition("/")[2] in HANDLER_CHECK_FILES
    }


def main() -> int:
    """Write the golden output of the example model, the shop model and the order portal."""
    if Path.cwd().resolve() != ROOT:
        print(f"Run this script from the folder {ROOT}.", file=sys.stderr)
        return 2
    for golden, model, configuration in GOLDENS:
        if golden.exists():
            shutil.rmtree(golden)
        golden.mkdir(parents=True)
        write_output(golden, model, configuration)
        print(f"Wrote {golden.relative_to(ROOT).as_posix()}.")
    HANDLER_CHECK.mkdir(parents=True, exist_ok=True)
    for name, content in handler_check_files().items():
        (HANDLER_CHECK / name).write_bytes(content)
    print(f"Wrote {HANDLER_CHECK.relative_to(ROOT).as_posix()}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
