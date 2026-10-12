// Test model of story #175: a react application calls an external API.
// The OpenAPI file of the external API is pet-store.openapi.json in this
// folder. The React generator writes the entity slices and the feature
// slices of the external API from the IR (PRD-APP-006).
package PetPortal {
    private import DSML::*;

    #Application part petPortal { :>> target = Target::react; }

    #ExternalApi part petStore {
        :>> openApiFile = "tests/models/react/external-api/pet-store.openapi.json";
    }

    #Calls dependency from petPortal to petStore;
}
