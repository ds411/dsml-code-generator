// Test model of story #65: TXT-001 accepts this model.
// The sentence of N-001 has 26 words in the text, but "trace link" is a term
// of the project dictionary and counts as one word. Thus it has 25 words.
package TxtAccept {
    private import DSML::*;
    @DsmlVersion { major = 1; minor = 0; }

    #Stakeholder part def Engineer;

    #Need concern <'N-001'> seeLinks {
        doc /*
         * The engineer must see each trace link from the need to the code,
         * the tests and the AWS resources in one HTML report for each environment.
         */
        subject;
        stakeholder engineer : Engineer;
    }

    #Requirement requirement <'R-001'> report {
        doc /* The toolchain must write a trace report. It must be in HTML. */
        frame seeLinks;
    }
}
