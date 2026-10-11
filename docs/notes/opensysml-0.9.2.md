# OpenSysML 0.9.2: results of the parse check

Story #12 examined the `opensysml` 0.9.2 Python client and `sysml-grpc` 0.9.2. This document gives the results. The tests are in `tests/test_opensysml_engine.py`. The test models are in `tests/models/opensysml/`. The adapter code is in `src/dsml/adapter/engine.py`.

## Summary

- `opensysml` 0.9.2 installs from PyPI with uv. It is a pure Python wheel. The license is Apache-2.0.
- The client downloads `sysml-grpc` one time and checks its SHA-256 hash. Then it starts `sysml-grpc` as a private child process.
- OpenSysML parses and resolves a metadata definition that specializes `Metaobjects::SemanticMetadata`, and a usage with a user-defined keyword.
- Each diagnostic gives the file, the line, the column, the severity, a code and a message.
- OpenSysML evaluates a constraint. The result is `holds`, `violated` or `undecided`. An `undecided` result names the feature that has no value.
- The tests found two limits that change the SysML sketch of the DSML. No result blocks the plan. See "Limits that change the DSML sketch".

## Installation

1. Add the dependency: `uv add opensysml==0.9.2`. `pyproject.toml` and `uv.lock` pin the version.
2. uv installs these runtime dependencies: `grpcio`, `protobuf` and `sigstore`, and the dependencies of `sigstore`. `grpcio` has wheels for Python 3.14 on Linux x64, Linux arm64 and macOS arm64.
3. The wheel does not contain `sysml-grpc`. At the first start, the client gets the binary. See "Supply of sysml-grpc".

## Supply of sysml-grpc

The client finds the binary in this sequence:

1. The path in the environment variable `OPENSYSML_BINARY`.
2. The cache file `~/.opensysml/bin/sysml-grpc`.
3. A download of the release of the client version, from `https://github.com/Open-MBEE/OpenSysML/releases/download/v0.9.2/sysml-grpc-<os>-<arch>`.
4. A `sysml-grpc` on `PATH`.

The client does a check of the downloaded binary against a SHA-256 hash in the wheel (`opensysml/release-digests.json`). If the hash is different, the client stops with `ChecksumMismatchError` and does not install the binary. This satisfies the hash check of PRD-CORE-049. The client also writes `~/.opensysml/bin/sysml-grpc.json` with the release tag and the hash.

The hashes of release v0.9.2 in the wheel are:

| Asset | SHA-256 |
| --- | --- |
| `sysml-grpc-linux-amd64` | `8577dacafa512416942639a3b2a7e38dc4a0bd89e64abce2e5e4faca581ee7c3` |
| `sysml-grpc-linux-arm64` | `289f3fdff259f1a49960abbdead31a9cd7bb4d3789430303d1823beffda1b3cf` |
| `sysml-grpc-darwin-arm64` | `f216818f2b37767d1aa7531a692612c7235e64ae9a21efe6b4de13d6832422f4` |
| `sysml-grpc-darwin-amd64` | `e0a899530c03dfc4364c472d04e3f8748338ae72132f75f9351b9d162c8cb2cc` |
| `sysml-grpc-windows-amd64.exe` | `d58a5b3ace4a627e59988b85d94d1b753ba7403b1477860f3ae2e8d83b3c3e99` |

Network use:

- The download uses the network one time. After the download, a start uses the cache and does not use the network. A test with a proxy that refuses all connections showed this.
- Without a cache and without a network, the start fails with `EngineError` ("Cannot start sysml-grpc: Failed to download binary ...").
- To work offline, put the binary in the cache before the work. The CI step "Start OpenSysML and measure the times" does this.
- The client does not do a hash check of a binary from `OPENSYSML_BINARY` or from `PATH`. The toolchain must not set `OPENSYSML_BINARY` for a release. The version check at start still applies to these binaries.

## Start of the child process

`opensysml.connect()` starts the child process with this command:

```text
sysml-grpc -port 0 -health-port 0 -report-address -exit-with-parent
```

- The kernel gives the port. The child writes the address on its standard output.
- The child reads the end of its standard input. When the Python process stops, the pipe closes and the child stops. This is correct also if the Python process stops with an error.
- One interpreter has one private service for each release. `Connection.close()` on the last connection stops the child.
- `opensysml.connect("host:port")` uses a service that somebody else started. The toolchain does not use this mode.
- The service reads a file path relative to its own working directory. Thus the adapter reads each file in Python and sends the text with a relative name (`Connection.parse_sources([(name, text), ...])`). The diagnostics then contain no absolute path (PRD-CORE-033).

## Version check

The adapter does two checks (PRD-CORE-018, PRD-CORE-019):

1. Before the start: `opensysml.__version__` must be the version in `src/dsml/versions.toml` ("0.9.2"). The client downloads only the release of its own version. Thus this check also stops a download of a different release.
2. After the start: `Connection.server_info().version` must be the release tag "v0.9.2".

If a check fails, the adapter raises `EngineVersionError`. The CLI must change this error into exit code 2. The CLI has no command that starts OpenSysML yet. A later story adds this.

The client also does a check: `opensysml.connect(version="v0.9.2")` raises `StaleServiceError` if the service has a different release.

## Form of the diagnostics

`Model.diagnostics` gives a list of diagnostics. Each diagnostic has these fields:

| Field | Example |
| --- | --- |
| `file` | `syntax-error.sysml` (the name that the adapter gave) |
| `start_line`, `start_column` | `4`, `39` (both start at 1) |
| `end_line`, `end_column` | `4`, `46` |
| `severity` | `error` or `warning` |
| `code` | `syntax`, `unresolved`, `feature-value-overriding`, `name-conflict` |
| `message` | `missing ';' at end of declaration` |

The adapter copies these fields into the data class `dsml.adapter.engine.Diagnostic`. It sorts the diagnostics by file, line, column, code and message (PRD-CORE-028). The `code` field is stable. Rules of the SYN category (PRD-CORE-021) must use the code, not the message text.

A syntax error does not stop the parse. OpenSysML gives a diagnostic and a model.

After a syntax error, OpenSysML does not report the names that it cannot resolve. Thus a model with a syntax error can have more errors.

Two members with the same name in one namespace give the warning `name-conflict` and no error. The SYN-002 test model uses this warning.

The module `dsml.adapter.findings` converts each diagnostic into a finding (PRD-CORE-021). The severity `error` gives SYN-001. Each other severity gives SYN-002. The finding message is the OpenSysML message, then the code. The module `dsml.rules` gives the message and the fix hint of each SYN rule (PRD-VAL-001).

## User-defined keywords

The test model `probe.sysml` has this metadata definition:

```sysml
abstract part databases : Database [*];
metadata def RelationalDatabase :> SemanticMetadata {
    :>> baseType = databases meta SysML::Usage;
}
#RelationalDatabase part auditDb;
```

- The model parses and resolves with no diagnostic (PRD-DSML-003).
- The expression `auditDb @ RelationalDatabase` gives `true`. Thus the adapter can find the keyword of an element.
- The expression `auditDb istype Database` gives `true`. Thus the keyword gives the base type to the usage.
- An unknown keyword, for example `#Unknown`, gives the error `unresolved reference: Unknown` with the code `unresolved`.
- The SysML v2 API JSON form (`Model.to_api_json()`) contains a `MetadataUsage` element with its type and its source position. OpenSysML marks this form as experimental.
- `Model.query()` does not give metadata usages.

## Evaluation of constraints

The adapter must evaluate each formal constraint one time for each environment (PRD-CORE-054, Q57). OpenSysML 0.9.2 gives three methods:

1. `Model.verify_constraint(name)` evaluates a constraint usage with the values in the model. The test constraint `prod.orderDb.multiAz == true` gives `holds`.
2. `Model.verify_requirement(name)` evaluates all the `require constraint` items of a requirement.
3. `Model.eval(expression, subject=name)` evaluates an expression in the context of an element.

To evaluate one constraint for each environment, use a requirement definition with the environment as its subject. Then make one requirement usage for each environment:

```sysml
requirement def OrderDataSafe {
    subject env : Environment;
    require constraint { env.orderDb.multiAz == true }
}
requirement orderDataSafeDev : OrderDataSafe { subject :>> env = dev; }
requirement orderDataSafeProd : OrderDataSafe { subject :>> env = prod; }
```

`orderDataSafeDev` gives `violated` and `orderDataSafeProd` gives `holds`. The adapter can also make these usages in the model text before the parse.

Do not use the argument `subject=` of `verify_constraint()` or `verify_requirement()` for this purpose. With `subject=`, OpenSysML 0.9.2 does not bind the subject parameter. The requirement gives `undecided` ("no value for feature env"), and a constraint definition with an `in` parameter gives `violated` for each environment.

The verdict has a `status` field. The adapter changes it into the result of PRD-CORE-054:

| `status` | Result |
| --- | --- |
| `holds` | `true` |
| `violated` | `false` |
| `undecided` | `unknown` |

An `undecided` verdict has an `error` text that names the feature with no value, for example `orderDb.storage has no value in the model`. The IR needs a list of feature names. OpenSysML gives only this text. The IR story (M2) must get the names from the text or from the constraint expression.

The questions `holds` and `satisfiable` of `verify_constraint()` need an SMT solver (z3 or cvc5). The toolchain does not need these questions.

## Limits that change the DSML sketch

These limits change the SysML sketch of the DSML, not a requirement. The stories #13 to #15 must use these results.

1. **A feature chain does not use the base type of a keyword.** In `feature-chain.sysml`, `orderDb` gets the type `Database` only from its keyword. The chain `orderDb.cpu` gives `unresolved member: cpu`. A redefinition in the body of the usage (`:>> cpu = 1024;`) resolves. Evaluation also uses the base type. To use a chain, give the usage an explicit type or subset, for example `#RelationalDatabase part orderDb :> databases;`. The example model has the chain `prod.orderDbProd.multiAz`. `orderDbProd` subsets `orderDbAws`, which has only a keyword.
2. **A value written with `=` is fixed.** A redefinition cannot change it. The error has the code `feature-value-overriding`. A value that an environment can change must use `default =`. The example model writes `:>> multiAz = false;` and `:>> desiredCount = 1;` on the AWS realizations, and the `prod` environment changes them. These lines must use `default =`.

A test examines each limit. If a new OpenSysML version removes a limit, its test fails.

Story #13 found more limits with the DSML library. See `docs/notes/dsml-library.md`.

## Times

`scripts/measure_opensysml.py` measures the times. Each parse uses a new service, because the service keeps a parsed model in memory. The values are medians of 5 runs. The parse of the example model and of the PRD model gives `unresolved` errors only, because the DSML library did not exist at the time of the measurement (story #12). These files have no syntax error.

| Platform | Start of `sysml-grpc` | Parse `probe.sysml` (51 lines) | Parse `order-service.sysml` (103 lines) | Parse PRD model (10 files, 1640 lines) |
| --- | --- | --- | --- | --- |
| Linux x64 (development container) | 103 ms | 31 ms | 107 ms | 1183 ms |
| Linux x64 (CI, `ubuntu-24.04`) | 123 ms | 38 ms | 139 ms | 1652 ms |
| Linux arm64 (CI, `ubuntu-24.04-arm`) | 72 ms | 22 ms | 101 ms | 1405 ms |
| macOS arm64 (CI, `macos-15`) | 82 ms | 11 ms | 64 ms | 1108 ms |

The first start includes the download of the binary (43 MB). It took 3.3 s in the development container, and from 1.1 s to 1.8 s in CI. The CI step "Start OpenSysML and measure the times" writes the times for each CI platform. The CI values are from the CI run of pull request #19.
