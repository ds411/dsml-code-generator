// Test model of story #163: STR-017 accepts this model.
// The OpenAPI file of the external API exists, and each item is in the subset.
package StrAccept {
    private import DSML::*;

    #ExternalApi part orderApi {
        :>> openApiFile = "tests/golden/fastapi/order-service/services/order-api/openapi.gen.json";
    }
}
