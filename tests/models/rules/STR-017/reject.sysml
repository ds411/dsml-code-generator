// Test model of story #163: STR-017 rejects this model.
// The OpenAPI file of the external API does not exist.
package StrReject {
    private import DSML::*;

    #ExternalApi part orderApi {
        :>> openApiFile = "tests/models/openapi/no-such-file.json";
    }
}
