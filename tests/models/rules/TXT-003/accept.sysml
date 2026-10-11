// Test model of story #65: TXT-003 accepts this model.
// Each requirement text has one "must". The word in `code` font is not a
// part of the text.
package TxtAccept {
    private import DSML::*;
    @DsmlVersion { major = 1; minor = 0; }

    #Requirement requirement <'R-001'> logs {
        doc /* The API must log each request with the flag `must log`. */
    }

    #Requirement requirement <'R-002'> users {
        doc /* The API must refuse a request from an unknown user. */
    }
}
