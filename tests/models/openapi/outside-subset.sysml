// Test model of story #163: the OpenAPI file of the external API has a
// header parameter. A header parameter is not in the subset of decision Q65.
// The adapter gives one STR-017 finding.
package OpenApiOutside {
    private import DSML::*;

    #ExternalApi part orderApi {
        :>> openApiFile = "tests/models/openapi/outside-subset.json";
    }
}
