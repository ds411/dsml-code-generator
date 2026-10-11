// Test model of story #65: TXT-003 rejects this model.
// The text of R-001 has two "must", so it contains two requirements.
package TxtReject {
    private import DSML::*;
    @DsmlVersion { major = 1; minor = 0; }

    #Requirement requirement <'R-001'> logs {
        doc /* The API must log each request. It Must refuse a request from an unknown user. */
    }
}
