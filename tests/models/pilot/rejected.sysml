// Test model of story #23: a library package with a construct that the OMG
// pilot implementation does not accept. The type "Undefined" does not
// resolve. The CI job "Pilot" makes sure that the pilot check fails for
// this file (PRD-DSML-005).
library package Rejected {
    private import Metaobjects::SemanticMetadata;

    metadata def Broken :> SemanticMetadata, Undefined;
}
