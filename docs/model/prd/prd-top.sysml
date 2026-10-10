package PrdTop {
    private import DSML::*;
    private import PrdNeeds::*;

    #Requirement requirement <'PRD-TOP-001'> top001 {
        doc /* The toolchain must be written in Python, and uv must manage the Python project. */
        :>> title = "Python and uv"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-TOP-002'> top002 {
        doc /* The toolchain must install as one Python package that supplies the command dsml. */
        :>> title = "One package"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-TOP-003'> top003 {
        doc /* The toolchain must run on the operating systems that decision record 03 gives. */
        :>> title = "Operating systems"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-TOP-004'> top004 {
        doc /* Validation, code generation and traceability must not use an AI model. */
        :>> title = "No AI model"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-TOP-005'> top005 {
        doc /* Validation, code generation and trace reports must not use the network. Only the local OpenSysML child process is permitted. */
        :>> title = "No network"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-TOP-006'> top006 {
        doc /* The toolchain must not write a secret value to a log, a report or a generated file. */
        :>> title = "No secrets in output"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-TOP-007'> top007 {
        doc /* Each dependency of the toolchain and of the generated code must have a license that the company accepts for internal software. */
        :>> title = "Accepted licenses"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-TOP-008'> top008 {
        doc /* Generated code must pin each dependency to the exact version that the version baseline gives. */
        :>> title = "Pinned dependencies"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-TOP-009'> top009 {
        doc /* The PRD set and the user documentation of the toolchain must use ASD-STE100 Issue 9. */
        :>> title = "STE documentation"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-TOP-010'> top010 {
        doc /* Each PRD requirement must have a unique ID with the prefix of its PRD. */
        :>> title = "Unique PRD IDs"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame traceability;
    }
    #Requirement requirement <'PRD-TOP-011'> top011 {
        doc /* The DSML appendix must contain each PRD requirement. OpenSysML must parse the appendix with no error. */
        :>> title = "DSML appendix parses"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame traceability;
    }
    #Requirement requirement <'PRD-TOP-012'> top012 {
        doc /* Validation and code generation of a model with 1,000 elements must finish in the time that decision record 03 gives. */
        :>> title = "Run time"; :>> kind = RequirementKind::performance; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
}
