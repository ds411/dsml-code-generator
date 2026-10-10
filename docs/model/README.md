# DSML model of the PRD set

These files write the product needs and each PRD requirement in the DSML, as one `.sysml` file for each PRD (two for the application generation PRD), plus one file for the needs. It is the first test of the DSML on a real set of requirements.

- The short name of each requirement is its PRD ID, for example `<'PRD-CORE-012'>`.
- Each requirement frames the product need that it serves most directly.
- All requirements have the priority `must` and the status `draft`, because no part is implemented yet.
- The text in each `doc` comment is the PRD text without code formatting. If the two are different, the PRD text is correct.
- OpenSysML 0.9.2 parses these files with no syntax error. The names do not resolve yet, because the DSML library does not exist yet ([notes](../notes/opensysml-0.9.2.md)). PRD-TOP-011 requires a parse with no error.

## Files

- [`prd/prd-needs.sysml`](prd/prd-needs.sysml)
- [`prd/prd-top.sysml`](prd/prd-top.sysml)
- [`prd/prd-dsml.sysml`](prd/prd-dsml.sysml)
- [`prd/prd-core.sysml`](prd/prd-core.sysml)
- [`prd/prd-app-common-fastapi.sysml`](prd/prd-app-common-fastapi.sysml)
- [`prd/prd-app-web.sysml`](prd/prd-app-web.sysml)
- [`prd/prd-iac.sysml`](prd/prd-iac.sysml)
- [`prd/prd-cicd.sysml`](prd/prd-cicd.sysml)
- [`prd/prd-val.sysml`](prd/prd-val.sysml)
- [`prd/prd-trace.sysml`](prd/prd-trace.sysml)
- [`examples/order-service.sysml`](examples/order-service.sysml): the example model of the DSML PRD. It parses and resolves with the DSML library with no diagnostic.
- [`syntax-changes.md`](syntax-changes.md): each change to the sketch syntax of the PRDs, and its reason.
