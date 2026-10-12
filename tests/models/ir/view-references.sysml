// A test model for the views with a wrong reference (story #159). OpenSysML
// gives only a warning for the view wrongTarget. The IR adapter gives a
// SYN-001 finding for each of the views noEntity, wrongTarget and noOperation.
package Wrong {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 1; }

    #Entity part def Order {
        #Key attribute id : Uuid [1];
    }

    // A part definition with no #Entity keyword.
    part def Note;

    #Operation action def PlaceOrder {
        in total : Decimal;
        :>> method = HttpMethod::post;
        :>> path = "/orders/place";
    }

    #Application part web {
        :>> target = Target::react;
        #View part noEntity {
            :>> kind = ViewKind::list;
            :>> 'public' = true;
        }
        #View part wrongTarget {
            :>> kind = ViewKind::detail;
            ref :>> entity : Note;
            :>> 'public' = true;
        }
        #View part noOperation {
            :>> kind = ViewKind::form;
            ref :>> entity : Order;
            :>> 'public' = true;
        }
        #View part noKind {
            :>> 'public' = true;
        }
        #View part correct {
            :>> kind = ViewKind::form;
            ref :>> operation : PlaceOrder;
            :>> 'public' = true;
        }
    }
}
