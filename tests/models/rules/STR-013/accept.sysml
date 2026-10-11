// STR-013 accepts this model. It has the changes of reject.sysml, with the
// #Destructive metadata on each change.
package Shop {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 0; }

    #Entity #Destructive part def Customer {
        #Key attribute id : Uuid [1];
        attribute name : String [1];
    }

    #Entity part def Article {
        @Destructive { renamedFrom = "Item"; }
        #Key attribute id : Uuid [1];
        attribute label : String [0..1] { @Destructive { renamedFrom = "title"; } }
        ref buyer : Customer [0..1];
    }

    #Application #Destructive part shopApi {
        :>> target = Target::fastapi;
        #Exposed part articles : Article [*];
    }
}
