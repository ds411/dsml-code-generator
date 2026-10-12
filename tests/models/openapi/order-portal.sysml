// Test model of story #163: a react application calls an external API.
// The OpenAPI file of the external API is the golden openapi.gen.json of the
// order service. The IR holds the entities and the operations of that file.
package OpenApiPortal {
    private import DSML::*;

    #Application part orderPortal { :>> target = Target::react; }

    #ExternalApi part orderApi {
        :>> openApiFile = "tests/golden/fastapi/order-service/services/order-api/openapi.gen.json";
    }

    #Calls dependency from orderPortal to orderApi;
}
