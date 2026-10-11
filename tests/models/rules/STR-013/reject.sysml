// STR-013 rejects this model. Compared with the snapshot in reject/, the
// model drops the column customer.email, renames the table item to article
// and drops the table legacy, with no #Destructive metadata.
package Shop {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 0; }

    #Entity part def Customer {
        #Key attribute id : Uuid [1];
        attribute name : String [1];
    }

    #Entity part def Article {
        #Key attribute id : Uuid [1];
        attribute label : String [0..1];
        ref buyer : Customer [0..1];
    }

    #Application part shopApi {
        :>> target = Target::fastapi;
        #Exposed part articles : Article [*];
    }
}
