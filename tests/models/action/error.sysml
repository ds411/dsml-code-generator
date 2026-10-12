// Error model of the GitHub Action test (story #137). SYN-001 rejects
// this model: line 6 has no ";" at the end.
package ActionError {
    private import ScalarValues::*;
    part def Database {
        attribute cpu : Integer
    }
}
