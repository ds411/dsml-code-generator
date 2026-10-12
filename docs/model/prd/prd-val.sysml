package PrdVal {
    private import DSML::*;
    private import PrdNeeds::*;

    #Requirement requirement <'PRD-VAL-001'> val001 {
        doc /* Each rule must be Python code that reads only the IR. Each rule must have an ID, a category, a default severity, a message and a fix hint. */
        :>> title = "Rule structure"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-VAL-002'> val002 {
        doc /* Rule IDs must have the form <CATEGORY>-<NNN>. A deleted rule ID must not be used again. */
        :>> title = "Rule IDs"; :>> kind = RequirementKind::'constraint'; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-VAL-003'> val003 {
        doc /* The severities must be error, warning and info. A finding with the severity error must stop code generation. */
        :>> title = "Severities"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-VAL-004'> val004 {
        doc /* The configuration file can increase the severity of a rule, or turn off a rule with the default severity warning or info. It must not decrease the severity of a rule with the default severity error or turn it off. */
        :>> title = "Severity configuration"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-VAL-005'> val005 {
        doc /* The option --fail-on warning must make dsml validate stop with exit code 1 if there is a warning. */
        :>> title = "Fail on warning"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-VAL-006'> val006 {
        doc /* The validator must write findings as text, as JSON, or as SARIF 2.1.0 with the rule metadata and the source locations. */
        :>> title = "Finding formats"; :>> kind = RequirementKind::'interface'; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-VAL-007'> val007 {
        doc /* The validator must sort findings by file, line, column and rule ID. */
        :>> title = "Sorted findings"; :>> kind = RequirementKind::'constraint'; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-VAL-008'> val008 {
        doc /* The toolchain CI must have, for each rule, one model that the rule accepts and one model that the rule rejects. */
        :>> title = "Rule tests"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-VAL-009'> val009 {
        doc /* A #Waiver must stop the findings of its rule on its element only. The report must list waived findings in a separate group, and SARIF must give them as suppressions with the reason. */
        :>> title = "Waiver effect"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-VAL-010'> val010 {
        doc /* After the expires date of a waiver, its findings must come back, and the validator must report rule STR-014. */
        :>> title = "Expired waivers"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-VAL-011'> val011 {
        doc /* The identity rules (category IDN) must run only when the user gives --baseline <git-ref> or the configuration file gives a default baseline. The validator must read the baseline model from the local Git repository. */
        :>> title = "Identity rules"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame traceability;
    }
    #Requirement requirement <'PRD-VAL-012'> val012 {
        doc /* The validator must read the result of each formal constraint for each environment from the IR (PRD-CORE-054). It reports rule FCN-001 for a false result and rule FCN-002 for an unknown result. */
        :>> title = "Formal constraint check"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-VAL-013'> val013 {
        doc /* The text rules (category TXT) must be off by default. The configuration file must be able to turn them on. */
        :>> title = "Optional text rules"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-VAL-014'> val014 {
        doc /* The text rules must use the project dictionary of the top-level PRD as a list of additional approved words. The toolchain must not claim full STE compliance. */
        :>> title = "Project dictionary in rules"; :>> kind = RequirementKind::'constraint'; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-VAL-015'> val015 {
        doc /* The validator must contain each rule in the catalog of the section "Rule catalog for phase 1", with its default severity. */
        :>> title = "Rule catalog"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-VAL-016'> val016 {
        doc /* Phase 2: the validator must contain each rule in the catalog of the section "Rule catalog additions for phase 2", with its default severity. */
        :>> title = "Phase 2 rule catalog"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
}
