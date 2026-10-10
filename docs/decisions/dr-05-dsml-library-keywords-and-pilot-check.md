# Decision record 05: DSML library keywords and the pilot check

Status date: 10 October 2026

## Purpose and status

This record holds 2 questions, Q59 and Q60, that came up in story #13 (the DSML library). Q59 changes PRD-DSML-009, and PRD-DSML-009 gives Q59 in the Source column. Q60 adds a story and changes no requirement.

Status: closed. On 10 October 2026, the product owner accepted the recommended answers of the decision issues #21 and #20.

## V. DSML library

Story #13 found that PRD-DSML-009 cannot apply to all keywords. OpenSysML 0.9.2 refuses semantic metadata on a dependency ("Cannot annotate Dependency"). Some metadata usages hold their own attributes, and a base type would give these attributes to the annotated element. See `docs/notes/dsml-library.md`.

| ID | Question and options | Selected answer | Status |
| --- | --- | --- | --- |
| Q59 | Which DSML keywords must specialize `Metaobjects::SemanticMetadata`? Options: (a) only the keywords of element kinds; a keyword on a dependency and a metadata definition that holds its own attributes is a plain metadata definition; (b) all keywords, with a different model form for the 7 other keywords, for example a part usage in place of a dependency for `#Realizes`. | (a). The other requirements already treat the 7 items as dependencies or metadata usages: `#Calls`, `#Realizes`, `#Uses`, `@Waiver`, `@DsmlVersion`, `@FieldRules` and `@Destructive`. Changed requirement: PRD-DSML-009. Decision issue #21. | Decided |
| Q60 | How does the toolchain verify PRD-DSML-005 (the OMG pilot implementation accepts the DSML library)? Options: (a) a CI job runs the library through a pinned release of the pilot Jupyter kernel; (b) a person runs the check before each library release; (c) change the verification method to "Inspection". | (a). It is the only option that agrees with the verification method "Test". Story #23 adds the job. No requirement changes. Decision issue #20. | Decided |
