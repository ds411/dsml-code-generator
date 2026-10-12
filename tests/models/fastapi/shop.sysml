// A test model for the CRUD slices of the FastAPI generator (story #84).
// It has the five CRUD operations, each field type, the field rules, a
// unique rule, a [1] relation, a [0..1] relation and a public entity. It
// also has custom operations with path parameters, a request body, query
// parameters, an entity output, a list output, a scalar output, no output
// and a public operation (story #88). The golden files in
// tests/golden/fastapi/shop/ are its output.
package Shop {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 0; }

    #Roles enum def ShopRoles { clerk; admin; }
    enum def ProductKind { book; music; video; }

    #Entity part def Supplier {
        #Key attribute id : Uuid [1];
        attribute name : String [1] { @FieldRules { minLength = 2; maxLength = 80; } }
    }

    #Entity part def Customer {
        #Key attribute id : Integer [1];
        attribute email : String [1] { @FieldRules { maxLength = 120; pattern = "^[a-z]+@[a-z]+[.]com$"; unique = true; } }
        attribute name : String [1] { @FieldRules { minLength = 2; maxLength = 80; } }
        attribute birthDate : Date [0..1];
        attribute vip : Boolean [1];
    }

    #Entity part def Product {
        #Key attribute id : Uuid [1];
        attribute code : String [1] { @FieldRules { pattern = "^[A-Z]{3}-[0-9]{4}$"; unique = true; } }
        attribute kind : ProductKind [1];
        attribute price : Decimal [1] { @FieldRules { minValue = 0; maxValue = 10000; precision = 10; scale = 2; } }
        attribute stock : Integer [1] { @FieldRules { minValue = 0; maxValue = 1000000; } }
        attribute weight : Real [0..1] { @FieldRules { minValue = 0.1; } }
        attribute addedAt : DateTime [0..1];
        attribute note : String [0..1];
        ref supplier : Supplier [1];
        ref buyer : Customer [0..1];
    }

    #Operation action def RestockProduct {
        in productId : Uuid;
        in amount : Integer;
        in note : String [0..1];
        out product : Product;
        :>> method = HttpMethod::post;
        :>> path = "/products/{productId}/restock";
    }

    #Operation action def FindProducts {
        in kind : ProductKind;
        in codes : String [0..*];
        out products : Product [0..*];
        :>> method = HttpMethod::get;
        :>> path = "/product-search";
    }

    #Operation action def CountCustomers {
        out total : Integer;
        out vipTotal : Integer;
        out newest : Date [0..1];
        :>> method = HttpMethod::get;
        :>> path = "/customer-count";
    }

    #Operation action def ArchiveSupplier {
        in supplier : Supplier;
        in reason : String;
        :>> method = HttpMethod::post;
        :>> path = "/suppliers/{supplier}/archive";
    }

    #Application part shopApi {
        :>> target = Target::fastapi;
        #Exposed part products : Product [*] {
            :>> crud = (CrudKind::create, CrudKind::read, CrudKind::update, CrudKind::delete, CrudKind::list);
            :>> allowedRoles = (ShopRoles::clerk, ShopRoles::admin);
        }
        #Exposed part customers : Customer [*] {
            :>> crud = (CrudKind::create, CrudKind::read, CrudKind::update, CrudKind::delete, CrudKind::list);
            :>> allowedRoles = (ShopRoles::admin);
        }
        #Exposed part suppliers : Supplier [*] {
            :>> crud = (CrudKind::create, CrudKind::read, CrudKind::list);
            :>> 'public' = true;
        }
        #Exposed action restockProduct : RestockProduct {
            :>> allowedRoles = (ShopRoles::clerk, ShopRoles::admin);
        }
        #Exposed action findProducts : FindProducts {
            :>> allowedRoles = (ShopRoles::clerk);
        }
        #Exposed action countCustomers : CountCustomers {
            :>> allowedRoles = (ShopRoles::admin);
        }
        #Exposed action archiveSupplier : ArchiveSupplier {
            :>> 'public' = true;
        }
    }
}
