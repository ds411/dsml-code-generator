// Test model of story #65: TXT-002 accepts this model.
// The requirement text uses "must" for an obligation and "can" for a
// possibility. The need text is not a requirement text, so "will" is
// permitted there.
package TxtAccept {
    private import DSML::*;
    @DsmlVersion { major = 1; minor = 0; }

    #Stakeholder part def Customer;

    #Need concern <'N-001'> fastAnswers {
        doc /* The customer will get an answer quickly. */
        subject;
        stakeholder customer : Customer;
    }

    #Requirement requirement <'R-001'> latency {
        doc /* The API must answer each request in 300 ms or less. The client can send a retry. */
        frame fastAnswers;
    }
}
