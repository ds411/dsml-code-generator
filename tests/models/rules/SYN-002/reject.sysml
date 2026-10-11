// Test model of story #29: SYN-002 rejects this model.
// Lines 5 and 6 give the same name to two members. OpenSysML gives the
// warning "name-conflict" and no error.
package SynReject {
    part def Database;
    part def Database;
}
