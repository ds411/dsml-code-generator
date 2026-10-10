// Test model of story #12: a small DSML-like model for OpenSysML 0.9.2.
// It has a metadata definition that specializes Metaobjects::SemanticMetadata,
// usages with a user-defined keyword, environments and require constraints.
package Probe {
    private import Metaobjects::SemanticMetadata;
    private import ScalarValues::*;

    part def Database {
        attribute multiAz : Boolean default = false;
        attribute cpu : Integer default = 512;
        attribute storage : Integer;
    }
    abstract part databases : Database [*];

    // The keyword #RelationalDatabase makes a usage a Database.
    metadata def RelationalDatabase :> SemanticMetadata {
        :>> baseType = databases meta SysML::Usage;
    }

    // A usage with only the keyword is a Database.
    #RelationalDatabase part auditDb;

    // OpenSysML 0.9.2 does not use the base type of the keyword to resolve a
    // feature chain such as "env.orderDb.multiAz". Thus "orderDb" also
    // subsets "databases". See feature-chain.sysml.
    part def Environment {
        #RelationalDatabase part orderDb :> databases;
    }

    part dev : Environment;
    part prod : Environment {
        part :>> orderDb { :>> multiAz = true; }
    }

    part plain;

    requirement def OrderDataSafe {
        subject env : Environment;
        require constraint { env.orderDb.multiAz == true }
    }
    requirement orderDataSafeDev : OrderDataSafe { subject :>> env = dev; }
    requirement orderDataSafeProd : OrderDataSafe { subject :>> env = prod; }

    requirement enoughStorage {
        require constraint storageSet { prod.orderDb.storage >= 20 }
    }

    constraint prodMultiAz { prod.orderDb.multiAz == true }
    constraint devMultiAz { dev.orderDb.multiAz == true }
    constraint prodStorage { prod.orderDb.storage >= 20 }
}
