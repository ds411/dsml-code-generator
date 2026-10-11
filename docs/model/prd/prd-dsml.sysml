package PrdDsml {
    private import DSML::*;
    private import PrdNeeds::*;

    #Requirement requirement <'PRD-DSML-001'> dsml001 {
        doc /* The DSML must be a SysML v2 model library package with the name DSML. */
        :>> title = "Library package"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-002'> dsml002 {
        doc /* The DSML must extend SysML v2 only with metadata definitions, attribute definitions and enumeration definitions. It must not add a concrete syntax. */
        :>> title = "No new syntax"; :>> kind = RequirementKind::'constraint'; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-003'> dsml003 {
        doc /* Each DSML element kind must be available as a user-defined keyword, for example #Need, #Entity and #ContainerService. */
        :>> title = "User-defined keywords"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-004'> dsml004 {
        doc /* OpenSysML must parse and resolve the DSML library with no error and no warning. */
        :>> title = "Library parses"; :>> kind = RequirementKind::'constraint'; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-DSML-005'> dsml005 {
        doc /* The DSML library must use only SysML v2 constructs that the OMG pilot implementation also accepts. */
        :>> title = "Pilot compatible"; :>> kind = RequirementKind::'constraint'; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-006'> dsml006 {
        doc /* The toolchain package must include the DSML library, so a model needs no download. */
        :>> title = "Library in package"; :>> kind = RequirementKind::'constraint'; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-DSML-007'> dsml007 {
        doc /* A model must be a set of .sysml files in one Git repository. The toolchain configuration file must give the files or folders of the model. */
        :>> title = "Model files in Git"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-008'> dsml008 {
        doc /* A model must import the DSML library with private import DSML::*; or refer to its elements with qualified names. */
        :>> title = "Library import"; :>> kind = RequirementKind::'interface'; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-009'> dsml009 {
        doc /* Each DSML keyword of an element kind must be a metadata definition that specializes Metaobjects::SemanticMetadata. Its base type must hold the attributes of the element kind. A keyword on a dependency, and a metadata definition that holds its own attributes, must be a plain metadata definition. */
        :>> title = "Semantic metadata"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-010'> dsml010 {
        doc /* The model must give attribute values with redefinitions of the base type features, for example :>> priority = Priority::must;. */
        :>> title = "Attribute values"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-011'> dsml011 {
        doc /* A stakeholder must be a part definition with the keyword #Stakeholder. */
        :>> title = "Stakeholder"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-012'> dsml012 {
        doc /* A need must be a concern usage with the keyword #Need. It must have one or more stakeholder members that refer to a stakeholder. */
        :>> title = "Need"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-013'> dsml013 {
        doc /* A need must have these attributes: ID (the short name), title, text (the doc comment), priority and status. */
        :>> title = "Need attributes"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-014'> dsml014 {
        doc /* A requirement must be a requirement usage with the keyword #Requirement. It can frame one or more needs with frame. */
        :>> title = "Requirement"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-015'> dsml015 {
        doc /* A requirement must have these attributes: ID (the short name), title, text (the doc comment), kind, priority and status. It can also have rationale, source and owner. */
        :>> title = "Requirement attributes"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-016'> dsml016 {
        doc /* The DSML must define these enumerations. Priority: must, should, could, wont. Status: draft, approved, implemented, verified, retired. RequirementKind: functional, performance, security, interface, constraint. */
        :>> title = "Enumerations"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-017'> dsml017 {
        doc /* A requirement derivation must use the #derivation connection of the SysML v2 RequirementDerivation library. A refinement must use a dependency with the #refinement metadata of the SysML v2 ModelingMetadata library. */
        :>> title = "Derivation and refinement"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame traceability;
    }
    #Requirement requirement <'PRD-DSML-018'> dsml018 {
        doc /* A requirement can contain formal constraints (require constraint) that refer to attributes of model elements. Quantities must use the SysML v2 quantity and unit libraries. */
        :>> title = "Formal constraints"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-DSML-019'> dsml019 {
        doc /* A project can add attributes to needs and requirements with a project library that specializes the DSML base types. */
        :>> title = "Project attributes"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-020'> dsml020 {
        doc /* An application must be a part usage with the keyword #Application. Its attribute target must have one of the values fastapi, react or nextjs. */
        :>> title = "Application"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-021'> dsml021 {
        doc /* A model can contain more than one application. */
        :>> title = "Several applications"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-022'> dsml022 {
        doc /* An entity must be a part definition with the keyword #Entity. Each attribute usage of an entity is a field. */
        :>> title = "Entity"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-023'> dsml023 {
        doc /* A field type must be one of: String, Integer, Boolean, Real from the SysML v2 libraries; Decimal, Date, DateTime and Uuid from the DSML library; or an enumeration definition in the model. */
        :>> title = "Field types"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-024'> dsml024 {
        doc /* An entity must have one primary key field with the keyword #Key. */
        :>> title = "Primary key"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-025'> dsml025 {
        doc /* A field multiplicity of [1] must mean a required field, and [0..1] an optional field. A field can have these DSML constraints: minLength, maxLength, minValue, maxValue, pattern, unique, and precision and scale for a Decimal field. */
        :>> title = "Field rules"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-026'> dsml026 {
        doc /* A relation between entities must be a reference usage typed by the related entity, with the multiplicity [0..1], [1] or [*]. A relation with [*] at the two ends is a many-to-many relation. */
        :>> title = "Relations"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-027'> dsml027 {
        doc /* An application must expose an entity with an entity usage that has the keyword #Exposed. Its attribute crud must list the CRUD operations: create, read, update, delete and list. */
        :>> title = "Exposed entities"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-028'> dsml028 {
        doc /* A custom operation must be an action definition with the keyword #Operation and typed in and out parameters. The toolchain must not read the body of the action. */
        :>> title = "Custom operation"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-029'> dsml029 {
        doc /* Each operation must have an HTTP method and a path. The DSML must give defaults for CRUD operations. A custom operation must state its method and path. */
        :>> title = "HTTP method and path"; :>> kind = RequirementKind::'interface'; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-030'> dsml030 {
        doc /* A react application must refer to the application whose API it calls, with a dependency that has the #Calls metadata. The two applications then use one API model. */
        :>> title = "Calls dependency"; :>> kind = RequirementKind::'interface'; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-031'> dsml031 {
        doc /* Phase 2: a view must be a part usage in an application with the keyword #View. Its attribute kind must be list, detail or form. A list or detail view must refer to one entity. A form view must refer to one operation. */
        :>> title = "View"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-032'> dsml032 {
        doc /* Phase 2: an application can give its navigation as an ordered list of views. */
        :>> title = "Navigation"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-033'> dsml033 {
        doc /* The roles of a model must be the values of one enumeration definition with the keyword #Roles. Each exposed operation, entity and view must list the roles that can use it in its attribute allowedRoles. The attribute value public = true must mean that no authentication is necessary. */
        :>> title = "Roles"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-034'> dsml034 {
        doc /* A destructive database change must have the #Destructive metadata on the changed entity or field. A rename must give the old name in the attribute renamedFrom. */
        :>> title = "Destructive changes"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-DSML-035'> dsml035 {
        doc /* A logical infrastructure element must be a part usage with one of the logical kinds in the table of the section "Infrastructure layer". */
        :>> title = "Logical kinds"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame cloudIndependence;
    }
    #Requirement requirement <'PRD-DSML-036'> dsml036 {
        doc /* A logical element must not contain an AWS term, an AWS attribute or an AWS service name. */
        :>> title = "No AWS terms in logical layer"; :>> kind = RequirementKind::'constraint'; :>> priority = Priority::must; :>> status = Status::draft;
        frame cloudIndependence;
    }
    #Requirement requirement <'PRD-DSML-037'> dsml037 {
        doc /* Each logical element must have one AWS realization: a part usage with the matching AWS kind and a dependency with the #Realizes metadata to the logical element. */
        :>> title = "AWS realization"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame cloudIndependence;
    }
    #Requirement requirement <'PRD-DSML-038'> dsml038 {
        doc /* An AWS realization must hold the AWS attributes, for example the RDS instance class or the Fargate CPU and memory. */
        :>> title = "AWS attributes"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame cloudIndependence;
    }
    #Requirement requirement <'PRD-DSML-039'> dsml039 {
        doc /* Each application must be allocated to one logical element with allocate. A fastapi or nextjs application must be allocated to a #ContainerService. A react application must be allocated to a #StaticSite. */
        :>> title = "Allocation"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-040'> dsml040 {
        doc /* A container service or a static site must refer to each database, user directory and secret store that it uses, with a dependency that has the #Uses metadata. */
        :>> title = "Uses dependency"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-041'> dsml041 {
        doc /* An environment must be a part usage with the keyword #Environment. It must have an AWS account ID, an AWS Region and a domain name. The model must contain the environments dev, staging and prod. */
        :>> title = "Environments"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-042'> dsml042 {
        doc /* An environment can change only these attributes of an AWS realization: cpu, memory, instanceClass, desiredCount, minCount, maxCount, multiAz and natGatewayCount. */
        :>> title = "Environment attributes"; :>> kind = RequirementKind::'constraint'; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-043'> dsml043 {
        doc /* The model must have one part usage with the keyword #ToolingAccount. It must have the AWS account ID and the AWS Region of the ECR repositories. */
        :>> title = "Tooling account"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-DSML-044'> dsml044 {
        doc /* A project must not add a logical kind or an AWS kind. A new kind must come in a new version of the DSML library. */
        :>> title = "Closed kind list"; :>> kind = RequirementKind::'constraint'; :>> priority = Priority::must; :>> status = Status::draft;
        frame cloudIndependence;
    }
    #Requirement requirement <'PRD-DSML-045'> dsml045 {
        doc /* A verification must be a verification usage with the keyword #Verification. It must have an ID (the short name), a title and a method. */
        :>> title = "Verification"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame traceability;
    }
    #Requirement requirement <'PRD-DSML-046'> dsml046 {
        doc /* The attribute method must have one of the values test, analysis, inspection or demonstration. */
        :>> title = "Verification methods"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame traceability;
    }
    #Requirement requirement <'PRD-DSML-047'> dsml047 {
        doc /* A verification must refer to each requirement that it verifies with verify in its objective. */
        :>> title = "Verify link"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame traceability;
    }
    #Requirement requirement <'PRD-DSML-048'> dsml048 {
        doc /* A verification with the method test must give one or more test file paths, relative to the repository root, in the attribute testFiles. */
        :>> title = "Test files"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame traceability;
    }
    #Requirement requirement <'PRD-DSML-049'> dsml049 {
        doc /* A verification can give test case names in the attribute testCases, for example a pytest node ID. */
        :>> title = "Test cases"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame traceability;
    }
    #Requirement requirement <'PRD-DSML-050'> dsml050 {
        doc /* Each need, requirement and verification must have a short name with the pattern of its kind: N-<NNN>, R-<NNN> or V-<NNN>. <NNN> has three or more digits with leading zeros. */
        :>> title = "ID patterns"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame traceability;
    }
    #Requirement requirement <'PRD-DSML-051'> dsml051 {
        doc /* A project can set different ID patterns in the toolchain configuration file. */
        :>> title = "Project ID patterns"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame traceability;
    }
    #Requirement requirement <'PRD-DSML-052'> dsml052 {
        doc /* Each short name must be unique in the model. A deleted ID must not be used again. */
        :>> title = "Unique IDs"; :>> kind = RequirementKind::'constraint'; :>> priority = Priority::must; :>> status = Status::draft;
        frame traceability;
    }
    #Requirement requirement <'PRD-DSML-053'> dsml053 {
        doc /* Each element without a short name must use its qualified name as its identity. */
        :>> title = "Qualified name identity"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame traceability;
    }
    #Requirement requirement <'PRD-DSML-054'> dsml054 {
        doc /* An element can have an OpenSysML IdentityMetadata::ElementId annotation. The DSML must not require it. */
        :>> title = "Optional ElementId"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame traceability;
    }
    #Requirement requirement <'PRD-DSML-055'> dsml055 {
        doc /* A waiver must be a #Waiver metadata usage on the element. It must have the attributes rule (the rule ID), reason and owner. It can have the attribute expires (a date). */
        :>> title = "Waiver"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-DSML-056'> dsml056 {
        doc /* The DSML library must have a semantic version. Each model must state the major and minor version of the library that it uses, with the #DsmlVersion metadata on its root package. */
        :>> title = "Library version"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-DSML-057'> dsml057 {
        doc /* A minor version of the DSML library must not make a valid model invalid. A major version must come with migration notes. */
        :>> title = "Compatible minor versions"; :>> kind = RequirementKind::'constraint'; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
}
