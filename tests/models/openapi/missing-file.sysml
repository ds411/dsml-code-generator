// Test model of story #163: the OpenAPI file of the external API does not
// exist. The adapter gives one STR-017 finding.
package OpenApiMissing {
    private import DSML::*;

    #ExternalApi part orderApi {
        :>> openApiFile = "tests/models/openapi/no-such-file.json";
    }
}
