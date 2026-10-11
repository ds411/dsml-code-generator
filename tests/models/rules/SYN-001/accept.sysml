// Test model of story #29: SYN-001 accepts this model.
// The syntax is correct, and each name resolves.
package SynAccept {
    part def Database {
        attribute cpu : ScalarValues::Integer;
    }
    part orderDb : Database;
}
