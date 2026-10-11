package PrdCicd {
    private import DSML::*;
    private import PrdNeeds::*;

    #Requirement requirement <'PRD-CICD-001'> cicd001 {
        doc /* The generator must write .github/workflows/pr.gen.yml, main.gen.yml and promote.gen.yml with the triggers and jobs in the table of the section "Workflows and jobs". */
        :>> title = "Three workflows"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CICD-002'> cicd002 {
        doc /* pr.gen.yml must run dsml validate and upload the SARIF findings to GitHub code scanning. */
        :>> title = "Validation in pull requests"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-CICD-003'> cicd003 {
        doc /* pr.gen.yml must run dsml generate --check and fail if a generated file is different from the committed file. */
        :>> title = "Determinism check"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CICD-004'> cicd004 {
        doc /* For each application, pr.gen.yml must install the dependencies from the committed lockfile (uv sync --frozen or pnpm install --frozen-lockfile), then run the linter, the type checker and the tests. A lockfile that does not agree with the dependency list must make the job fail. */
        :>> title = "Build and test"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CICD-005'> cicd005 {
        doc /* pr.gen.yml must run dsml check-output. */
        :>> title = "Output checks in CI"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-CICD-006'> cicd006 {
        doc /* pr.gen.yml must run tofu plan for dev with the plan role, and write the plan text in the job summary. It must not apply. */
        :>> title = "Plan in pull requests"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-CICD-007'> cicd007 {
        doc /* main.gen.yml must build each container image and the static files of each React application one time. It must then deploy them to dev. */
        :>> title = "Build once"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CICD-008'> cicd008 {
        doc /* promote.gen.yml must deploy the image digests and the static files of one main build to staging, then to prod. It must not build again. */
        :>> title = "Promotion"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CICD-009'> cicd009 {
        doc /* Each deploy job must use a concurrency group for its environment, so only one deployment runs in an environment at a time. A new run must not cancel a running deployment. */
        :>> title = "Deployment concurrency"; :>> kind = RequirementKind::'constraint'; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CICD-010'> cicd010 {
        doc /* Workflows must get AWS credentials only through GitHub OIDC and the roles of PRD-IAC-027 and PRD-IAC-028. They must not use long-term access keys. */
        :>> title = "OIDC credentials"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CICD-011'> cicd011 {
        doc /* Each job must declare the smallest permissions set that it needs. Only jobs that use AWS must have id-token: write. */
        :>> title = "Job permissions"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CICD-012'> cicd012 {
        doc /* Each deploy job must use the GitHub environment of its target environment (dev, staging or prod). */
        :>> title = "GitHub environments"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CICD-013'> cicd013 {
        doc /* The generator must write a README with the settings that a repository administrator must make: the GitHub environments, required reviewers for prod, and branch protection for the main branch. */
        :>> title = "Repository settings"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CICD-014'> cicd014 {
        doc /* Each third-party action must be pinned to a full commit SHA from the version baseline, with its version in a comment. */
        :>> title = "Pinned actions"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CICD-015'> cicd015 {
        doc /* Workflows must not write secret values to logs or job summaries. Values from AWS outputs that are not secret can appear in summaries. */
        :>> title = "No secrets in CI logs"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CICD-016'> cicd016 {
        doc /* A deploy job must run tofu apply with the image digests of the build and model_commit set to the commit of the build. */
        :>> title = "Apply step"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame traceability;
    }
    #Requirement requirement <'PRD-CICD-017'> cicd017 {
        doc /* After the apply, the job must run the migration task definition of each application with a database as a one-off ECS task, and wait for it. If the task fails, the job must stop before it changes a service. */
        :>> title = "Migration step"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CICD-018'> cicd018 {
        doc /* After the migrations, the job must set each ECS service to its new task definition and wait for a steady state. If the ECS deployment circuit breaker rolls back, the job must fail. */
        :>> title = "Rollout step"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CICD-019'> cicd019 {
        doc /* Phase 2: for each React application, the job must upload the static files to its S3 bucket, write /config.json from the outputs of the root module, and invalidate the CloudFront cache. */
        :>> title = "Static site step"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CICD-020'> cicd020 {
        doc /* promote.gen.yml must deploy to prod only after the staging deployment of the same build succeeded and a required reviewer approved the prod environment. */
        :>> title = "Prod gate"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-CICD-021'> cicd021 {
        doc /* Each deploy job must write a job summary with the environment, the image digests, the model commit and the applied migrations. */
        :>> title = "Deployment summary"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame traceability;
    }
}
