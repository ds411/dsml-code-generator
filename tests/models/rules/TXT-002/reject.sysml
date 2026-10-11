// Test model of story #65: TXT-002 rejects this model.
// R-001 uses "shall", R-002 uses "should" and "may", and R-003 uses "will".
package TxtReject {
    private import DSML::*;
    @DsmlVersion { major = 1; minor = 0; }

    #Requirement requirement <'R-001'> latency {
        doc /* The API shall answer each request in 300 ms or less. */
    }

    #Requirement requirement <'R-002'> retry {
        doc /* The client should send a retry. It May wait one second. */
    }

    #Requirement requirement <'R-003'> logs {
        doc /* The API will log each request. */
    }
}
