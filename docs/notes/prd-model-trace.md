# Validation and trace of the PRD model

Story #138 makes the toolchain validate and trace its own PRD model in CI. The PRD model is in `docs/model/prd/`.

- Validation configuration: `docs/model/prd/dsml.toml`.
- Trace configuration: `dsml-prd.toml` in the root folder of the repository.
- CI steps: "Validate the PRD model", "Write the trace reports of the PRD model" and "Keep the trace reports of the PRD model" in `.github/workflows/ci.yml`. The CI artifact `prd-trace-reports` keeps `coverage.html` and `orphans.html`.
- Tests: `tests/test_prd_model.py`.

## Commands

Run these commands in the root folder of the repository:

```sh
uv run dsml validate --config docs/model/prd/dsml.toml
uv run dsml trace coverage --config dsml-prd.toml --output coverage.html
uv run dsml trace orphans --config dsml-prd.toml --output orphans.html
```

## Gap in the configuration (PRD-TRACE-010)

The toolchain reads trace comments only in the output folders and in the test folders of the configuration file (PRD-TRACE-010). Each path in the configuration file is relative to the folder of the configuration file. The configuration reader in `src/dsml/config.py` does not accept a path with `..`. Thus `docs/model/prd/dsml.toml` cannot name the folders `src/` and `tests/` of the repository.

The solution is a second configuration file, `dsml-prd.toml`, in the root folder. It has the same model and the same ID patterns as `docs/model/prd/dsml.toml`, and the key `trace.tests` names `src` and `tests`. The test `test_trace_configuration_agrees_with_the_model_configuration` makes sure that the two files agree.

These are the limits of this solution:

- The key `trace.tests` names folders for hand-written tests, but `src/` contains no tests. This has no effect on the reports. The orphans report finds a test file from its name, for example `test_*.py`, not from its folder.
- The configuration cannot exclude a folder. The toolchain also reads the golden files in `tests/golden/`. These files are the output of other models, thus their trace comments give orphans. The section "Orphans" gives them.

The product owner must decide if the configuration must get a key for a list of excluded folders, or a key for source folders. This is not in story #138.

## Trace comments on more than one line

Before story #138, 20 trace comments in `src/` and `tests/` continued on a second line with no `trace:` marker, for example:

```python
# trace: PRD-CORE-001, PRD-CORE-006, PRD-TRACE-010, PRD-TRACE-012, PRD-TRACE-013,
# PRD-TRACE-016, PRD-TRACE-017, PRD-TRACE-018
```

The form of PRD-TRACE-009 has one line. The reader thus gave a warning for the empty item after the last comma, and it did not read the IDs on the second line. Story #138 puts the marker `trace:` on each line. The test `test_trace_comments_of_the_toolchain_are_correct` makes sure that the reader reads each trace comment of the toolchain with no warning.

## Result

The result is for commit `f442c18` of `main` with the changes of story #138.

### Validation

`dsml validate` finds 0 errors, 0 warnings and 0 info findings. The golden findings in `tests/golden/validate/prd.findings.txt` give the same result.

### Coverage

The PRD model has 311 requirements. Each requirement has a need.

| Status | Requirements |
| --- | --- |
| `missing` | 311 |
| `satisfied` | 0 |
| `verified` | 0 |

The status of each requirement is `missing`, because the PRD model has no satisfy links and no verify links. These links are not in story #138.

235 requirements have one or more trace comments in `src/` or `tests/`. 76 requirements have no trace comment:

| Part | Requirements with no trace comment |
| --- | --- |
| APP | 51 of 92 |
| CICD | 1 of 21 |
| CORE | 5 of 54 |
| DSML | 7 of 57 |
| IAC | 5 of 42 |
| TOP | 7 of 12 |
| TRACE | 0 of 18 |
| VAL | 0 of 15 |

### Orphans

The orphans report has 81 items:

| Category | Items | Cause |
| --- | --- | --- |
| `test-file-without-verification` | 58 | The test files `tests/test_*.py`. The PRD model has no verification elements. |
| `test-file-without-verification` | 17 | The golden test files in `tests/golden/fastapi/`. |
| `unknown-trace-id` | 6 | The golden files in `tests/golden/fastapi/`. The IDs are elements of other models. |

The report has no trace comment in `src/` or in `tests/test_*.py` with an ID that is not in the PRD model. These are the 6 trace comments with an unknown ID:

| ID | Location | Model of the ID |
| --- | --- | --- |
| `OrderService::CancelOrder` | `tests/golden/fastapi/handler-check/handler.py:20` | `docs/model/examples/order-service.sysml` |
| `OrderService::CancelOrder` | `tests/golden/fastapi/order-service/services/order-api/app/features/order/cancel_order/handler.py:20` | `docs/model/examples/order-service.sysml` |
| `Shop::ArchiveSupplier` | `tests/golden/fastapi/shop/services/shop-api/app/features/supplier/archive_supplier/handler.py:20` | `tests/models/fastapi/shop.sysml` |
| `Shop::CountCustomers` | `tests/golden/fastapi/shop/services/shop-api/app/features/count_customers/count_customers/handler.py:23` | `tests/models/fastapi/shop.sysml` |
| `Shop::FindProducts` | `tests/golden/fastapi/shop/services/shop-api/app/features/product/find_products/handler.py:20` | `tests/models/fastapi/shop.sysml` |
| `Shop::RestockProduct` | `tests/golden/fastapi/shop/services/shop-api/app/features/product/restock_product/handler.py:23` | `tests/models/fastapi/shop.sysml` |

These comments are correct in their own models. They are not errors in the toolchain code, thus no correction is necessary.
