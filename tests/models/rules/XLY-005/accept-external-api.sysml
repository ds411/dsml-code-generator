// Test model of story #163: XLY-005 accepts this model.
// The react application calls an external API with #Calls. The external API
// gives an imported OpenAPI file.
package XlyAccept {
    private import DSML::*;

    #Application part orderPortal { :>> target = Target::react; }

    #ExternalApi part orderApi {
        :>> openApiFile = "tests/golden/fastapi/order-service/services/order-api/openapi.gen.json";
    }

    #Calls dependency from orderPortal to orderApi;
}
