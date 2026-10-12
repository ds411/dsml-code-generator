package PrdAi {
    private import DSML::*;
    private import PrdNeeds::*;

    #Requirement requirement <'PRD-AI-001'> ai001 {
        doc /* The toolchain package must contain two skills in the Agent Skills format: the modeling skill dsml-modeling and the CLI skill dsml-cli. */
        :>> title = "Two skills in the package"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-AI-002'> ai002 {
        doc /* The modeling skill must tell an AI agent how to write a model in the five layers with the DSML keywords. It must contain the rule catalog and example models. */
        :>> title = "Modeling skill"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-AI-003'> ai003 {
        doc /* The CLI skill must tell an AI agent how to use dsml init, validate, generate, check-output and trace. It must give a loop that corrects the findings until dsml validate finds no error. */
        :>> title = "CLI skill"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-AI-004'> ai004 {
        doc /* The command dsml skills install must write the two skills into the folder .claude/skills/ of the project. The option --output must select a different folder. */
        :>> title = "Skills install command"; :>> kind = RequirementKind::'interface'; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-AI-005'> ai005 {
        doc /* dsml skills install must replace only the skill folders that it owns. It must not change a different file or folder in the destination folder. */
        :>> title = "Install changes only skill folders"; :>> kind = RequirementKind::'constraint'; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-AI-006'> ai006 {
        doc /* Two runs of dsml skills install with the same toolchain version must write byte-identical files. */
        :>> title = "Deterministic skills install"; :>> kind = RequirementKind::'constraint'; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-AI-007'> ai007 {
        doc /* The reference files of the skills must agree with the DSML library, the rule catalog and the CLI of the same toolchain version. A CI test must find a reference file that is not current. */
        :>> title = "Current skill references"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-AI-008'> ai008 {
        doc /* The command dsml mcp must start a local MCP server with the official MCP Python SDK. The server must use only the stdio transport. */
        :>> title = "Local MCP server"; :>> kind = RequirementKind::'interface'; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-AI-009'> ai009 {
        doc /* The MCP Python SDK must be in the optional dependency group mcp of the toolchain package. Without the group, dsml mcp must stop with exit code 2 and a message that gives the install command. */
        :>> title = "Optional MCP dependency group"; :>> kind = RequirementKind::'constraint'; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-AI-010'> ai010 {
        doc /* All other subcommands must operate without the optional dependency group mcp. */
        :>> title = "Core without MCP group"; :>> kind = RequirementKind::'constraint'; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-AI-011'> ai011 {
        doc /* The MCP server must have the MCP tools init, validate, ir, generate, check_output, trace and version. Each tool must accept the options of its subcommand, except --output and --overwrite. */
        :>> title = "MCP tools"; :>> kind = RequirementKind::'interface'; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-AI-012'> ai012 {
        doc /* For the same model, configuration and toolchain version, each MCP tool must give the same result as its subcommand. */
        :>> title = "Same results as the CLI"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-AI-013'> ai013 {
        doc /* Only the MCP tools init and generate can write files. The tool generate must obey PRD-CORE-042 and PRD-CORE-043, and it must stop on a changed generated file. */
        :>> title = "Files that MCP tools write"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-AI-014'> ai014 {
        doc /* The MCP server must operate only in the project folder that the user gives when the server starts. It must refuse a path outside that folder and must not write a file outside it. */
        :>> title = "Project folder only"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-AI-015'> ai015 {
        doc /* The MCP server must have MCP resources that give the DSML reference, the rule catalog and the example models. The resources must use the same reference files as the skills. */
        :>> title = "MCP resources"; :>> kind = RequirementKind::'interface'; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-AI-016'> ai016 {
        doc /* The MCP server must have MCP prompts for these tasks: write a model from a product description, correct the findings of validation, and generate code. */
        :>> title = "MCP prompts"; :>> kind = RequirementKind::'interface'; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-AI-017'> ai017 {
        doc /* The MCP server must not use the network and must not send the model to a different computer. It must not open a network socket. */
        :>> title = "No network in MCP server"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-AI-018'> ai018 {
        doc /* The text of the skills, the MCP tools, the MCP resources and the MCP prompts must use ASD-STE100 Issue 9. */
        :>> title = "STE text for agents"; :>> kind = RequirementKind::'constraint'; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
}
