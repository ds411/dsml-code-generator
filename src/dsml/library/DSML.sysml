// The DSML library, version 1.0.0.
//
// trace: PRD-DSML-001, PRD-DSML-002, PRD-DSML-003, PRD-DSML-009, PRD-DSML-056
//
// A model imports the library with "private import DSML::*;". Each element
// kind is a metadata definition. A model uses it as a user-defined keyword,
// for example "#Need" or "#ContainerService".
//
// Two forms of metadata definition are in this library:
//
// 1. A keyword for an element kind specializes
//    Metaobjects::SemanticMetadata. Its base type is an abstract usage in
//    the package BaseTypes. The base type holds the attributes of the kind.
//    The model gives the attribute values with redefinitions, for example
//    ":>> priority = Priority::must;".
// 2. A keyword that annotates a dependency, and a metadata usage that holds
//    its own attributes (for example @Waiver), is a plain metadata
//    definition. OpenSysML 0.9.2 does not accept semantic metadata on a
//    dependency (docs/notes/dsml-library.md).
//
// The library uses only metadata definitions, attribute definitions,
// enumeration definitions and the base types of the keywords. It adds no
// concrete syntax.
library package DSML {
    private import ScalarValues::*;
    private import Metaobjects::SemanticMetadata;

    // trace: PRD-DSML-056
    @DsmlVersion { major = 1; minor = 0; patch = 0; }

    // ------------------------------------------------------------------
    // Attribute types (PRD-DSML-023)
    // ------------------------------------------------------------------

    // trace: PRD-DSML-023
    attribute def Decimal :> Real {
        doc /* A decimal number. The FieldRules attributes precision and scale give its digits. */
    }
    attribute def Date :> String {
        doc /* A calendar date in the ISO 8601 form YYYY-MM-DD. */
    }
    attribute def DateTime :> String {
        doc /* A date and a time of day in the ISO 8601 form, with a time zone offset. */
    }
    attribute def Uuid :> String {
        doc /* A universally unique identifier (RFC 9562) in its text form. */
    }

    // ------------------------------------------------------------------
    // Enumerations
    // ------------------------------------------------------------------

    // trace: PRD-DSML-016
    enum def Priority { must; should; could; wont; }

    // trace: PRD-DSML-016
    enum def Status { draft; approved; implemented; verified; retired; }

    // trace: PRD-DSML-016
    // "interface" and "constraint" are SysML keywords, so the definition
    // writes them as unrestricted names. A model must also write them with
    // quotes, for example RequirementKind::'constraint' (story #27).
    enum def RequirementKind { functional; performance; security; 'interface'; 'constraint'; }

    // trace: PRD-DSML-020
    enum def Target { fastapi; react; nextjs; }

    // trace: PRD-DSML-027
    enum def CrudKind { create; read; update; delete; list; }

    // trace: PRD-DSML-029
    enum def HttpMethod { get; post; put; patch; delete; }

    // trace: PRD-DSML-046
    // "analysis" is a SysML keyword, so the definition writes it as an
    // unrestricted name. A model must write VerificationMethod::'analysis'.
    enum def VerificationMethod { test; 'analysis'; inspection; demonstration; }

    // ------------------------------------------------------------------
    // Default HTTP method and path of each CRUD operation (PRD-DSML-029)
    // ------------------------------------------------------------------

    // trace: PRD-DSML-029
    attribute def CrudDefault {
        doc /*
         * The default HTTP method and path of a CRUD operation. In the path,
         * {entities} is the collection name of the exposed entity, and {id}
         * is the value of its key field.
         */
        attribute crud : CrudKind;
        attribute method : HttpMethod;
        attribute path : String;
    }

    // trace: PRD-DSML-029
    attribute crudDefaults : CrudDefault [5] = (
        new CrudDefault(crud = CrudKind::create, method = HttpMethod::post, path = "/{entities}"),
        new CrudDefault(crud = CrudKind::read, method = HttpMethod::get, path = "/{entities}/{id}"),
        new CrudDefault(crud = CrudKind::update, method = HttpMethod::patch, path = "/{entities}/{id}"),
        new CrudDefault(crud = CrudKind::delete, method = HttpMethod::delete, path = "/{entities}/{id}"),
        new CrudDefault(crud = CrudKind::list, method = HttpMethod::get, path = "/{entities}")
    );

    // ------------------------------------------------------------------
    // Base types of the keywords
    // ------------------------------------------------------------------

    package BaseTypes {
        doc /*
         * The base types of the DSML keywords. A project library can
         * specialize these definitions to add attributes (PRD-DSML-019).
         */

        // Needs and requirements layers

        // trace: PRD-DSML-011
        part def Stakeholder;
        abstract part stakeholders : Stakeholder [*];

        // trace: PRD-DSML-012, PRD-DSML-013
        concern def Need {
            attribute title : String;
            attribute priority : Priority;
            attribute status : Status;
        }
        abstract concern needs : Need [*];

        // trace: PRD-DSML-014, PRD-DSML-015
        requirement def Requirement {
            attribute title : String;
            attribute kind : RequirementKind;
            attribute priority : Priority;
            attribute status : Status;
            attribute rationale : String [0..1];
            attribute source : String [0..1];
            attribute owner : String [0..1];
        }
        abstract requirement requirements : Requirement [*];

        // Application layer

        // trace: PRD-DSML-020
        part def Application {
            attribute target : Target;
        }
        abstract part applications : Application [*];

        // trace: PRD-DSML-022
        part def Entity;
        abstract part entities : Entity [*];

        // trace: PRD-DSML-024
        abstract attribute keys [*];

        // trace: PRD-DSML-005, PRD-DSML-027, PRD-DSML-033
        // An exposed element is an entity usage (a part) or an operation
        // usage (an action). Thus the base type is an occurrence usage with
        // no definition. The pilot implementation does not accept an action
        // usage with a type that is not an action definition.
        abstract occurrence exposures [*] {
            attribute crud : CrudKind [0..*];
            attribute allowedRoles : Roles [0..*];
            attribute 'public' : Boolean default = false;
        }

        // trace: PRD-DSML-028, PRD-DSML-029
        action def Operation {
            attribute method : HttpMethod;
            attribute path : String;
        }
        abstract action operations : Operation [*];

        // trace: PRD-DSML-033
        // The roles enumeration of a model specializes this definition.
        attribute def Roles;
        abstract attribute roles : Roles [*];

        // Infrastructure layer: logical elements

        // trace: PRD-DSML-035
        part def LogicalElement;

        part def Network :> LogicalElement;
        abstract part networks : Network [*];

        part def ContainerService :> LogicalElement;
        abstract part containerServices : ContainerService [*];

        part def RelationalDatabase :> LogicalElement;
        abstract part relationalDatabases : RelationalDatabase [*];

        part def UserDirectory :> LogicalElement;
        abstract part userDirectories : UserDirectory [*];

        part def SecretStore :> LogicalElement;
        abstract part secretStores : SecretStore [*];

        // Infrastructure layer: AWS realizations

        // trace: PRD-DSML-037, PRD-DSML-038, PRD-DSML-042
        // Only the attributes of PRD-DSML-042 are in the AWS kinds of
        // version 1.0.0. An environment can change each of them.
        part def AwsRealization;
        abstract part awsRealizations : AwsRealization [*];

        part def AwsVpc :> AwsRealization {
            attribute natGatewayCount : Natural [0..1];
        }
        abstract part awsVpcs : AwsVpc [*] :> awsRealizations;

        part def AwsEcsService :> AwsRealization {
            attribute cpu : Positive [0..1];
            attribute memory : Positive [0..1];
            attribute desiredCount : Natural [0..1];
            attribute minCount : Natural [0..1];
            attribute maxCount : Natural [0..1];
        }
        abstract part awsEcsServices : AwsEcsService [*] :> awsRealizations;

        part def AwsRdsPostgres :> AwsRealization {
            attribute instanceClass : String [0..1];
            attribute multiAz : Boolean [0..1];
        }
        abstract part awsRdsPostgresDatabases : AwsRdsPostgres [*] :> awsRealizations;

        part def AwsCognito :> AwsRealization;
        abstract part awsCognitoUserPools : AwsCognito [*] :> awsRealizations;

        part def AwsSecrets :> AwsRealization;
        abstract part awsSecretStores : AwsSecrets [*] :> awsRealizations;

        // trace: PRD-DSML-041, PRD-DSML-042
        // An override is a part usage in an environment. It subsets an AWS
        // realization and redefines the attributes that the environment
        // changes.
        abstract part overrides : AwsRealization [*];

        // trace: PRD-DSML-041
        part def Environment {
            attribute accountId : String;
            attribute region : String;
            attribute domain : String;
        }
        abstract part environments : Environment [*];

        // trace: PRD-DSML-043
        part def ToolingAccount {
            attribute accountId : String;
            attribute region : String;
        }
        abstract part toolingAccounts : ToolingAccount [*];

        // Verification layer

        // trace: PRD-DSML-045, PRD-DSML-046, PRD-DSML-048, PRD-DSML-049
        verification def Verification {
            attribute title : String;
            attribute method : VerificationMethod;
            attribute testFiles : String [0..*];
            attribute testCases : String [0..*];
        }
        abstract verification verifications : Verification [*];
    }

    // ------------------------------------------------------------------
    // Keywords of the needs and requirements layers
    // ------------------------------------------------------------------

    // trace: PRD-DSML-011
    metadata def Stakeholder :> SemanticMetadata {
        doc /* A stakeholder. Use it on a part definition. */
        :>> baseType = BaseTypes::stakeholders meta SysML::Usage;
    }

    // trace: PRD-DSML-012, PRD-DSML-013
    metadata def Need :> SemanticMetadata {
        doc /* A stakeholder need. Use it on a concern usage. */
        :>> baseType = BaseTypes::needs meta SysML::Usage;
    }

    // trace: PRD-DSML-014, PRD-DSML-015
    metadata def Requirement :> SemanticMetadata {
        doc /* A requirement. Use it on a requirement usage. */
        :>> baseType = BaseTypes::requirements meta SysML::Usage;
    }

    // ------------------------------------------------------------------
    // Keywords of the application layer
    // ------------------------------------------------------------------

    // trace: PRD-DSML-020
    metadata def Application :> SemanticMetadata {
        doc /* An application. Use it on a part usage. */
        :>> baseType = BaseTypes::applications meta SysML::Usage;
    }

    // trace: PRD-DSML-022
    metadata def Entity :> SemanticMetadata {
        doc /* An entity. Use it on a part definition. Each attribute usage is a field. */
        :>> baseType = BaseTypes::entities meta SysML::Usage;
    }

    // trace: PRD-DSML-024
    metadata def Key :> SemanticMetadata {
        doc /* The primary key field of an entity. Use it on an attribute usage. */
        :>> baseType = BaseTypes::keys meta SysML::Usage;
    }

    // trace: PRD-DSML-027, PRD-DSML-033
    metadata def Exposed :> SemanticMetadata {
        doc /*
         * An entity or an operation that an application exposes. Use it on
         * a part usage of an entity or on an action usage of an operation.
         */
        :>> baseType = BaseTypes::exposures meta SysML::Usage;
    }

    // trace: PRD-DSML-028, PRD-DSML-029
    metadata def Operation :> SemanticMetadata {
        doc /* A custom operation. Use it on an action definition. */
        :>> baseType = BaseTypes::operations meta SysML::Usage;
    }

    // trace: PRD-DSML-030
    metadata def Calls {
        doc /* The application that the client of the dependency calls. Use it on a dependency. */
    }

    // trace: PRD-DSML-033
    metadata def Roles :> SemanticMetadata {
        doc /* The roles of the model. Use it on one enumeration definition. */
        :>> baseType = BaseTypes::roles meta SysML::Usage;
    }

    // trace: PRD-DSML-034
    metadata def Destructive {
        doc /*
         * A destructive database change. Use it on an entity or on a field.
         * For a rename, give the old name in renamedFrom.
         */
        attribute renamedFrom : String [0..1];
    }

    // trace: PRD-DSML-025
    metadata def FieldRules {
        doc /*
         * The constraints of a field. Use it as a metadata usage in the body
         * of the field. Give only the constraints that apply.
         */
        attribute minLength : Natural [0..1];
        attribute maxLength : Natural [0..1];
        attribute minValue : Real [0..1];
        attribute maxValue : Real [0..1];
        attribute pattern : String [0..1];
        attribute unique : Boolean [0..1];
        attribute precision : Positive [0..1];
        attribute scale : Natural [0..1];
    }

    // ------------------------------------------------------------------
    // Keywords of the infrastructure layer
    // ------------------------------------------------------------------

    // trace: PRD-DSML-035
    metadata def Network :> SemanticMetadata {
        doc /* A logical network. Use it on a part usage. */
        :>> baseType = BaseTypes::networks meta SysML::Usage;
    }

    // trace: PRD-DSML-035
    metadata def ContainerService :> SemanticMetadata {
        doc /* A logical container service. Use it on a part usage. */
        :>> baseType = BaseTypes::containerServices meta SysML::Usage;
    }

    // trace: PRD-DSML-035
    metadata def RelationalDatabase :> SemanticMetadata {
        doc /* A logical relational database. Use it on a part usage. */
        :>> baseType = BaseTypes::relationalDatabases meta SysML::Usage;
    }

    // trace: PRD-DSML-035
    metadata def UserDirectory :> SemanticMetadata {
        doc /* A logical user directory. Use it on a part usage. */
        :>> baseType = BaseTypes::userDirectories meta SysML::Usage;
    }

    // trace: PRD-DSML-035
    metadata def SecretStore :> SemanticMetadata {
        doc /* A logical secret store. Use it on a part usage. */
        :>> baseType = BaseTypes::secretStores meta SysML::Usage;
    }

    // trace: PRD-DSML-037
    metadata def AwsVpc :> SemanticMetadata {
        doc /* The AWS realization of a network. Use it on a part usage. */
        :>> baseType = BaseTypes::awsVpcs meta SysML::Usage;
    }

    // trace: PRD-DSML-037
    metadata def AwsEcsService :> SemanticMetadata {
        doc /* The AWS realization of a container service. Use it on a part usage. */
        :>> baseType = BaseTypes::awsEcsServices meta SysML::Usage;
    }

    // trace: PRD-DSML-037
    metadata def AwsRdsPostgres :> SemanticMetadata {
        doc /* The AWS realization of a relational database. Use it on a part usage. */
        :>> baseType = BaseTypes::awsRdsPostgresDatabases meta SysML::Usage;
    }

    // trace: PRD-DSML-037
    metadata def AwsCognito :> SemanticMetadata {
        doc /* The AWS realization of a user directory. Use it on a part usage. */
        :>> baseType = BaseTypes::awsCognitoUserPools meta SysML::Usage;
    }

    // trace: PRD-DSML-037
    metadata def AwsSecrets :> SemanticMetadata {
        doc /* The AWS realization of a secret store. Use it on a part usage. */
        :>> baseType = BaseTypes::awsSecretStores meta SysML::Usage;
    }

    // trace: PRD-DSML-037
    metadata def Realizes {
        doc /*
         * The AWS realization of a logical element. Use it on a dependency
         * from the AWS realization to the logical element.
         */
    }

    // trace: PRD-DSML-040
    metadata def Uses {
        doc /*
         * A database, user directory or secret store that a container
         * service or a static site uses. Use it on a dependency.
         */
    }

    // trace: PRD-DSML-041
    metadata def Environment :> SemanticMetadata {
        doc /* A deployment environment. Use it on a part usage. */
        :>> baseType = BaseTypes::environments meta SysML::Usage;
    }

    // trace: PRD-DSML-042
    metadata def Override :> SemanticMetadata {
        doc /*
         * A change of an AWS realization in one environment. Use it on a
         * part usage in the environment that subsets the AWS realization.
         */
        :>> baseType = BaseTypes::overrides meta SysML::Usage;
    }

    // trace: PRD-DSML-043
    metadata def ToolingAccount :> SemanticMetadata {
        doc /* The AWS account and Region of the ECR repositories. Use it on a part usage. */
        :>> baseType = BaseTypes::toolingAccounts meta SysML::Usage;
    }

    // ------------------------------------------------------------------
    // Keywords of the verification layer, waivers and versions
    // ------------------------------------------------------------------

    // trace: PRD-DSML-045
    metadata def Verification :> SemanticMetadata {
        doc /* A verification. Use it on a verification usage. */
        :>> baseType = BaseTypes::verifications meta SysML::Usage;
    }

    // trace: PRD-DSML-055
    metadata def Waiver {
        doc /*
         * A waiver of one validation rule for the annotated element. The
         * attribute expires is optional.
         */
        attribute rule : String;
        attribute reason : String;
        attribute owner : String;
        attribute expires : Date [0..1];
    }

    // trace: PRD-DSML-056
    metadata def DsmlVersion {
        doc /*
         * The version of the DSML library. A model gives the major and the
         * minor version on its root package. The library also gives the
         * patch version.
         */
        attribute major : Natural;
        attribute minor : Natural;
        attribute patch : Natural [0..1];
    }
}
