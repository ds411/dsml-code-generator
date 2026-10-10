package PrdAppCommonFastApi {
    private import DSML::*;
    private import PrdNeeds::*;

    // Rules for all targets
    #Requirement requirement <'PRD-APP-001'> app001 {
        doc /* Each application generator must read only the IR. */
        :>> title = "IR only"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-002'> app002 {
        doc /* For each application in the IR, the generator of its target must write the code in the output folder that the configuration file gives for that application. */
        :>> title = "Output folder"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-003'> app003 {
        doc /* A generator must write code only for the entities, operations, views and roles in the IR, and for the health endpoint of PRD-APP-012. */
        :>> title = "Only modeled code"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame traceability;
    }
    #Requirement requirement <'PRD-APP-004'> app004 {
        doc /* A FastAPI or Next.js application must also write an OpenAPI 3.1 document, openapi.gen.json, from the IR. The OpenAPI document that the running service supplies must agree with it. */
        :>> title = "OpenAPI document"; :>> kind = RequirementKind::interface; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-005'> app005 {
        doc /* The client types of a React application and the schemas of the API that it calls must come from the same IR entities and operations. A contract test in the toolchain CI must compare the generated client with the openapi.gen.json of the called application. */
        :>> title = "One API model"; :>> kind = RequirementKind::interface; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-APP-006'> app006 {
        doc /* Phase 2: a React application can call an external API that an imported OpenAPI file gives, in place of an application in the model. */
        :>> title = "External API import"; :>> kind = RequirementKind::interface; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-APP-007'> app007 {
        doc /* Each application must authenticate users with the Amazon Cognito user pool of its environment. Web clients must use Cognito managed login with the authorization code flow and PKCE. */
        :>> title = "Cognito login"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-008'> app008 {
        doc /* For each operation, the generated server code must examine the access token. It must return HTTP 401 if there is no valid token, and HTTP 403 if no group in the cognito:groups claim is in allowedRoles. An operation with public = true must need no token. */
        :>> title = "Server role check"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-009'> app009 {
        doc /* The generated web client must show only the navigation items and views that the roles of the user permit. It must send a user with no session to the login page. The server check of PRD-APP-008 stays the protection. */
        :>> title = "Client role check"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-010'> app010 {
        doc /* Each application must read its environment values at run time, not at build time. One build or one container image must operate in all environments. */
        :>> title = "Run-time configuration"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-011'> app011 {
        doc /* Each application must get secret values from environment variables that ECS sets from Secrets Manager. Generated code must not contain a secret value. */
        :>> title = "Secrets from ECS"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-012'> app012 {
        doc /* A FastAPI or Next.js application must supply GET /healthz with no authentication. It must return HTTP 200 while the process operates. */
        :>> title = "Health endpoint"; :>> kind = RequirementKind::interface; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-013'> app013 {
        doc /* The Dockerfile of a FastAPI or Next.js application must use a multi-stage build and a base image pinned by digest. The container must run as a user that is not root and must not contain a secret value. */
        :>> title = "Dockerfile"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-014'> app014 {
        doc /* API errors must use problem details (RFC 9457) with the media type application/problem+json. */
        :>> title = "Problem details"; :>> kind = RequirementKind::interface; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-015'> app015 {
        doc /* Server logs must be JSON lines on standard output, with a request ID in each line. Logs must not contain tokens or secret values. */
        :>> title = "Server logs"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-016'> app016 {
        doc /* The generated code of each target must pass dsml check-output with no error. */
        :>> title = "Output checks pass"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-APP-017'> app017 {
        doc /* Each generated source file must have the trace header that the traceability PRD gives. */
        :>> title = "Trace header"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame traceability;
    }

    // FastAPI target (phase 1)
    #Requirement requirement <'PRD-APP-101'> app101 {
        doc /* The FastAPI target must use Python, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic and pytest, and uv must manage the project. The versions must come from the version baseline. */
        :>> title = "FastAPI stack"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-102'> app102 {
        doc /* The generator must write one slice folder for each operation: app/features/<entity>/<operation>/. A slice must contain endpoint_gen.py (the router) and schemas_gen.py (the Pydantic models). */
        :>> title = "Vertical slices"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-103'> app103 {
        doc /* For a CRUD operation, the generator must write the handler as handler_gen.py. For a custom operation, it must write handler.py as a create-once stub. */
        :>> title = "Handlers"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-104'> app104 {
        doc /* Code that all slices use must be in app/shared/: the database session, the SQLAlchemy models, the Cognito token check, the configuration and the error types. */
        :>> title = "Shared code"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-105'> app105 {
        doc /* app/main_gen.py must create the FastAPI application and register the router of each slice in sorted order. */
        :>> title = "Main module"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-106'> app106 {
        doc /* A generated file in a slice must import only from its own slice and from app/shared/. */
        :>> title = "Slice imports"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-110'> app110 {
        doc /* Each operation in the IR must have one endpoint with the HTTP method and the path of the operation. CRUD operations must use the default methods and paths in the table of the section "API operations and schemas" unless the model gives a different method or path. */
        :>> title = "Endpoints"; :>> kind = RequirementKind::interface; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-111'> app111 {
        doc /* For each exposed entity, the generator must write Pydantic v2 models for create input, update input and output. The key field must not be in the create input. Each field of the update input must be optional. */
        :>> title = "Pydantic models"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-112'> app112 {
        doc /* Field rules must become Pydantic field constraints: minLength and maxLength to min_length and max_length, minValue and maxValue to ge and le, and pattern to pattern. */
        :>> title = "Field constraints"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-113'> app113 {
        doc /* A request that breaks a field rule must get HTTP 422. A request that breaks a unique rule must get HTTP 409. A request for an entity that does not exist must get HTTP 404. */
        :>> title = "Error status codes"; :>> kind = RequirementKind::interface; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-114'> app114 {
        doc /* A list operation must accept limit (default 50, maximum 200) and offset (default 0). It must return the found entities in items, sorted by key, and their count in total. */
        :>> title = "List paging"; :>> kind = RequirementKind::interface; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-115'> app115 {
        doc /* An output schema must give a related entity as its key, not as a nested object. */
        :>> title = "Related entity keys"; :>> kind = RequirementKind::interface; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-116'> app116 {
        doc /* For a custom operation, the generated endpoint must validate the input, check the roles, open a database session and then call handle(input, session, user) in handler.py. It must return the output that handle gives as the output schema. */
        :>> title = "Custom operation endpoint"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-117'> app117 {
        doc /* The create-once handler.py stub must contain the typed handle function. Its body must raise NotImplementedError, so the endpoint returns HTTP 501 until a developer writes the logic. */
        :>> title = "Handler stub"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-120'> app120 {
        doc /* For each entity, the generator must write one typed SQLAlchemy 2 model in app/shared/db/models/<entity>_gen.py. The table name must be the entity name in snake case. */
        :>> title = "SQLAlchemy models"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-121'> app121 {
        doc /* Field types must map to PostgreSQL types as the table of the section "Data access and migrations" gives. */
        :>> title = "Type map"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-122'> app122 {
        doc /* A [*] to [*] relation must have a generated join table. A [0..1] or [1] relation must have a foreign key. */
        :>> title = "Relation tables"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-123'> app123 {
        doc /* Database access must use the SQLAlchemy mode and the database driver that decision record 03 gives. */
        :>> title = "Database access mode"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-124'> app124 {
        doc /* The generator must keep the schema snapshot in .dsml/schema-snapshot.json. If the IR schema is different from the snapshot, the generator must write one new Alembic migration and then update the snapshot. */
        :>> title = "Schema snapshot"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-125'> app125 {
        doc /* A migration file must have the name migrations/versions/<NNNN>_<slug>_gen.py. Its revision ID must come from its content and its number, not from a random value or the clock. */
        :>> title = "Deterministic migrations"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-126'> app126 {
        doc /* The generator must keep each migration file that it wrote before, byte for byte. */
        :>> title = "Migration history"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-127'> app127 {
        doc /* The generator must not write a migration that drops or renames a table or a column, unless the IR has the #Destructive metadata for that change. */
        :>> title = "Destructive migrations"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-APP-128'> app128 {
        doc /* app/migrate_gen.py must apply all migrations that the database does not have, and then stop. The deployment runs it as decision record 03 gives. */
        :>> title = "Migration command"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-130'> app130 {
        doc /* app/shared/auth/cognito_gen.py must supply a FastAPI dependency. It must check the signature of the access token against the JWKS of the user pool, and the claims iss, token_use (access), client_id and exp. */
        :>> title = "Token check"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-131'> app131 {
        doc /* The dependency must keep the JWKS in memory and get it again only when a token has an unknown key ID. */
        :>> title = "JWKS cache"; :>> kind = RequirementKind::performance; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-132'> app132 {
        doc /* app/shared/config_gen.py must read the configuration from environment variables at start. If a mandatory variable is missing, the application must stop with a message that names the variable. */
        :>> title = "Configuration module"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-133'> app133 {
        doc /* The Dockerfile must install the locked dependencies with uv sync --frozen --no-dev and run Uvicorn on port 8000. */
        :>> title = "FastAPI container"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-134'> app134 {
        doc /* The fixed-name generated files of the FastAPI target must be: pyproject.toml, Dockerfile, .dockerignore, alembic.ini, migrations/env.py and each __init__.py in a generated folder. */
        :>> title = "FastAPI fixed names"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-135'> app135 {
        doc /* pytest must run on the generated project with no error when the project has no tests. */
        :>> title = "Empty test run"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
}
