package PrdCore {
    private import DSML::*;
    private import PrdNeeds::*;

    #Requirement requirement <'PRD-CORE-001'> core001 {
        doc /* The command dsml must have the subcommands and options in the table above. */
        :>> title = "Subcommands"; :>> kind = RequirementKind::interface; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-CORE-002'> core002 {
        doc /* Each subcommand must stop with exit code 0 if it finds no error, 1 if it finds an error finding or a --check difference, and 2 if a usage error or an internal error occurs. */
        :>> title = "Exit codes"; :>> kind = RequirementKind::interface; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-CORE-003'> core003 {
        doc /* dsml generate must validate the model first. If there is an error finding, it must stop and write no file. */
        :>> title = "Validate before generate"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-CORE-004'> core004 {
        doc /* dsml generate --check must write no file. It must list each file that a normal run would add, change or delete. */
        :>> title = "Check mode"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-005'> core005 {
        doc /* dsml generate must generate only one part of the output when the user gives --application <name>, --infrastructure or --pipelines. */
        :>> title = "Partial generation"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-006'> core006 {
        doc /* Each subcommand must write its report to standard output, or to the file that --output gives. */
        :>> title = "Report output"; :>> kind = RequirementKind::interface; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-CORE-007'> core007 {
        doc /* A message about a model location must give the file path, the line and the column. */
        :>> title = "Message locations"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-CORE-008'> core008 {
        doc /* Messages to the user must use ASD-STE100 Issue 9. */
        :>> title = "STE messages"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-CORE-009'> core009 {
        doc /* A subcommand must not ask for input from a terminal. */
        :>> title = "No prompts"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-010'> core010 {
        doc /* The option --verbose must write debug messages to standard error. */
        :>> title = "Verbose option"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-CORE-011'> core011 {
        doc /* dsml check-output must run tsc, ruff, tofu validate, tflint and the FSD linter Steiger on the generated code of the selected targets. It must report a missing tool as an error with the tool name. */
        :>> title = "Output checks"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-CORE-012'> core012 {
        doc /* The toolchain must read its configuration from dsml.toml in the repository root, or from the file that the option --config gives. */
        :>> title = "Configuration file"; :>> kind = RequirementKind::interface; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-013'> core013 {
        doc /* The configuration file must give: the model files or folders; the output folder of each application, of the infrastructure and of the pipelines; the ID patterns; the optional rule sets; the default trace baseline; and the IaC options for one tool only. */
        :>> title = "Configuration content"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-014'> core014 {
        doc /* The configuration file must have a schema version. The toolchain must report an unknown key or an unknown schema version as an error. */
        :>> title = "Configuration schema"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-015'> core015 {
        doc /* Environment variables, the user name, the host name, the locale, the time zone and the clock must not change the generated output. */
        :>> title = "No environment input"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-016'> core016 {
        doc /* The configuration file must not contain secret values. */
        :>> title = "No secrets in configuration"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-017'> core017 {
        doc /* The toolchain must call OpenSysML through the opensysml Python client. The client must start sysml-grpc as a private child process. */
        :>> title = "OpenSysML client"; :>> kind = RequirementKind::interface; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-CORE-018'> core018 {
        doc /* The toolchain must pin one OpenSysML version for the Python package and the sysml-grpc binary. The version must come from the version baseline. */
        :>> title = "OpenSysML version pin"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-019'> core019 {
        doc /* At start, the toolchain must compare the version of sysml-grpc with the pinned version. If they are different, it must stop with exit code 2. */
        :>> title = "OpenSysML version check"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-020'> core020 {
        doc /* Only the IR adapter module must import the opensysml package. A lint rule in the toolchain CI must enforce this. */
        :>> title = "One adapter module"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-CORE-021'> core021 {
        doc /* The adapter must convert each OpenSysML diagnostic into a finding of the category SYN of the validation PRD. */
        :>> title = "Diagnostics as findings"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-CORE-022'> core022 {
        doc /* The IR must be JSON. The toolchain package must contain the JSON Schema of the IR. */
        :>> title = "IR format"; :>> kind = RequirementKind::interface; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-023'> core023 {
        doc /* The IR must have a semantic version in the field irVersion. A change that removes or renames a field must increase the major version. */
        :>> title = "IR version"; :>> kind = RequirementKind::interface; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-024'> core024 {
        doc /* The IR must hold each element of the five layers, its DSML attributes, its trace links and its source location (file, line, column). */
        :>> title = "IR content"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame traceability;
    }
    #Requirement requirement <'PRD-CORE-025'> core025 {
        doc /* The IR must not contain an OpenSysML type, an OpenSysML object or an OpenSysML internal ID. */
        :>> title = "Engine-neutral IR"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-026'> core026 {
        doc /* Validators and generators must read only the IR. They get the results of formal constraints from the IR (PRD-CORE-054), not from OpenSysML. */
        :>> title = "IR only"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-027'> core027 {
        doc /* The toolchain CI must compare the IR of each reference model with a stored golden IR file. A change of the OpenSysML version must pass this comparison before a release. */
        :>> title = "Golden IR tests"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-028'> core028 {
        doc /* The same model, configuration file and toolchain version must give byte-identical generated files, IR, reports and trace manifests on each supported operating system. */
        :>> title = "Byte-identical output"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-029'> core029 {
        doc /* The toolchain CI must run each reference model on Linux x64, Linux arm64 and macOS arm64, and compare the outputs byte by byte. */
        :>> title = "Cross-platform comparison"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-030'> core030 {
        doc /* The toolchain CI must compare the output of each reference model with stored golden files. */
        :>> title = "Golden files"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-031'> core031 {
        doc /* Generators must write each list in an output file in a defined order: by element identity, then by name. */
        :>> title = "Sorted lists"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-032'> core032 {
        doc /* The output must not depend on the order of the model files on disk or in the configuration file. */
        :>> title = "File order independence"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-033'> core033 {
        doc /* The output must not contain a timestamp, a random value, an absolute path, a user name or a host name. */
        :>> title = "No variable values"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-034'> core034 {
        doc /* Each output file must use UTF-8 with no byte order mark, LF line ends and one LF at the end of the file. */
        :>> title = "Text encoding"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-035'> core035 {
        doc /* Templates must give their output in the format of the pinned formatter for the file type: Prettier for TypeScript, ruff format for Python, tofu fmt for HCL. The generator must not run a formatter. The toolchain CI must run each formatter in check mode on the golden files and find no change. */
        :>> title = "Formatted templates"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-036'> core036 {
        doc /* The generator must not write lockfiles (uv.lock, pnpm-lock.yaml, .terraform.lock.hcl). The generated CI makes them, and Git keeps them. */
        :>> title = "No lockfiles"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-037'> core037 {
        doc /* A minor or patch release of the toolchain must not change the output for an unchanged model, except to fix a defect that its release notes name. */
        :>> title = "Stable minor releases"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-038'> core038 {
        doc /* The header of a generated file must give the major version of the toolchain only. */
        :>> title = "Major version in header"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-039'> core039 {
        doc /* A generated file must have a name that ends with .gen.<ext> or _gen.py, or be on the fixed-name list of its target. Each generation PRD gives its fixed-name list, for example pyproject.toml, package.json, Dockerfile and the Next.js app/ folder. */
        :>> title = "Generated file names"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-040'> core040 {
        doc /* The generator must keep a manifest in .dsml/generated.json. For each generated file, it must give the path and the SHA-256 hash. For each create-once file, it must give the path. */
        :>> title = "Generated file manifest"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-041'> core041 {
        doc /* At each run, the generator must delete each generated file of the old manifest that the new run does not write. */
        :>> title = "Delete stale files"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-042'> core042 {
        doc /* The generator must not write, change or delete a file that is not a generated file of the old or new manifest, except a new create-once file. */
        :>> title = "Hand-written files stay"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-043'> core043 {
        doc /* If the hash of a generated file is different from its hash in the manifest, dsml generate must stop with an error that lists the changed files. The option --overwrite must replace them. */
        :>> title = "Changed generated files"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-044'> core044 {
        doc /* The generator must write a create-once file only if no file exists at its path. */
        :>> title = "Create-once files"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-045'> core045 {
        doc /* Generated code must call hand-written code through a typed interface, for example a handler function with typed parameters. A difference between the two must cause a type check error. */
        :>> title = "Typed extension points"; :>> kind = RequirementKind::interface; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-046'> core046 {
        doc /* The generator must own the dependency lists of each target. A developer must add a dependency in the configuration file, not in a generated file. */
        :>> title = "Dependency lists"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-047'> core047 {
        doc /* The toolchain must be a Python package that uv builds. The release process must publish it to the internal package index. A user must be able to install it with uv tool install. */
        :>> title = "Python package"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-CORE-048'> core048 {
        doc /* The package must contain the DSML library, the IR schema, the templates and the pinned copy of the shadcn/ui components. */
        :>> title = "Package content"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-049'> core049 {
        doc /* The installation must supply the sysml-grpc binary of the pinned OpenSysML version and check its SHA-256 hash against the release checksums of OpenSysML. */
        :>> title = "Checked engine binary"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-050'> core050 {
        doc /* The toolchain must supply a GitHub Action that installs a pinned toolchain version and runs one subcommand. */
        :>> title = "GitHub Action"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-051'> core051 {
        doc /* When its input sarif is true, the GitHub Action must upload the SARIF findings to GitHub code scanning. */
        :>> title = "SARIF upload"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-CORE-052'> core052 {
        doc /* Toolchain releases must use semantic versioning. The release notes must name each change to the generated output. */
        :>> title = "Semantic versioning"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CORE-053'> core053 {
        doc /* Before each release, the toolchain CI must generate and deploy each reference model to a sandbox AWS account, and remove it after the test. */
        :>> title = "Sandbox deployment test"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-CORE-054'> core054 {
        doc /* The adapter must evaluate each formal constraint of a requirement through OpenSysML, one time for each environment, and write each result into the IR. The evaluation uses the attribute values of that environment. A result is true, false or unknown. An unknown result gives the features that have no value. */
        :>> title = "Constraint results in the IR"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
}
