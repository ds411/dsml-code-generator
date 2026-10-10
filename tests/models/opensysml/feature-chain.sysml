// Test model of story #12: a known limit of OpenSysML 0.9.2.
// "orderDb" gets the type Database only from the keyword #RelationalDatabase.
// The feature chain "orderDb.cpu" on line 14 does not resolve.
package FeatureChain {
    private import Metaobjects::SemanticMetadata;

    part def Database { attribute cpu : ScalarValues::Integer default = 512; }
    abstract part databases : Database [*];
    metadata def RelationalDatabase :> SemanticMetadata {
        :>> baseType = databases meta SysML::Usage;
    }

    #RelationalDatabase part orderDb;
    attribute orderDbCpu = orderDb.cpu;
}
