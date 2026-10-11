// Test model of story #65: TXT-001 rejects this model.
// The second sentence of N-001 has 28 words, and the sentence of R-001
// has 28 words.
package TxtReject {
    private import DSML::*;
    @DsmlVersion { major = 1; minor = 0; }

    #Stakeholder part def Engineer;

    #Need concern <'N-001'> seeLinks {
        doc /*
         * The engineer must see the links. The engineer must see each link
         * from the need to the code, the tests and the AWS resources in one
         * HTML report for each environment of the model.
         */
        subject;
        stakeholder engineer : Engineer;
    }

    #Requirement requirement <'R-001'> report {
        doc /*
         * The toolchain must write one HTML report with each link from each
         * need to the code, the tests and the AWS resources of each
         * environment of the model.
         */
        frame seeLinks;
    }
}
