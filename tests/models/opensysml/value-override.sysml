// Test model of story #12: a value written with "=" is fixed.
// Line 10 tries to change the fixed value "multiAz = false" of line 9.
// Line 11 changes a value written with "default =", which is correct.
package ValueOverride {
    part def Database {
        attribute multiAz : ScalarValues::Boolean;
        attribute cpu : ScalarValues::Integer;
    }
    part orderDb : Database { :>> multiAz = false; :>> cpu default = 512; }
    part orderDbProd :> orderDb { :>> multiAz = true; }
    part orderDbDev :> orderDb { :>> cpu = 256; }
}
