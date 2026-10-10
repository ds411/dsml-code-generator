package PrdAppWeb {
    private import DSML::*;
    private import PrdNeeds::*;

    // React target (phase 2)
    #Requirement requirement <'PRD-APP-201'> app201 {
        doc /* The React target must use strict TypeScript, pnpm, Vite, React, TanStack Router, TanStack Query, TanStack Form, Zod, Tailwind CSS, shadcn/ui and Amplify Auth. The versions must come from the version baseline. */
        :>> title = "React stack"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-202'> app202 {
        doc /* The generator must put the code in the FSD layers app, pages, widgets, features, entities and shared in src/. */
        :>> title = "FSD layers"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-203'> app203 {
        doc /* Generated code must obey the FSD import rules: a module imports only from lower layers, and only through the public API of a slice. */
        :>> title = "FSD import rules"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-204'> app204 {
        doc /* Each slice must have a create-once index.ts that re-exports the generated index.gen.ts. */
        :>> title = "Slice public API"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-205'> app205 {
        doc /* The path alias @/ must refer to src/. */
        :>> title = "Path alias"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-206'> app206 {
        doc /* Slice names and file names must be the kebab case of the model element names. */
        :>> title = "Slice names"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame traceability;
    }
    #Requirement requirement <'PRD-APP-210'> app210 {
        doc /* The generator must put each model element in the slice and the files that the table above gives. */
        :>> title = "FSD map"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-211'> app211 {
        doc /* The Zod schemas of an entity must apply the same field rules as the Pydantic models of PRD-APP-112. */
        :>> title = "Zod field rules"; :>> kind = RequirementKind::interface; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-APP-212'> app212 {
        doc /* The generator must write the shadcn/ui components that the templates use into shared/ui as create-once files, from the pinned copy in the toolchain package. */
        :>> title = "shadcn/ui components"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-220'> app220 {
        doc /* The generator must write the TanStack Router route tree with code-based routing in src/app/router/routes.gen.tsx. The project must not use the TanStack Router file-based routing plugin. */
        :>> title = "Code-based routes"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-221'> app221 {
        doc /* Each view must have one route. A list view must use the path /<entities>, a detail view /<entities>/$id, and a form view /<operation>. */
        :>> title = "Route paths"; :>> kind = RequirementKind::interface; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-222'> app222 {
        doc /* The beforeLoad function of each route must check the session and the roles of the view. With no session, it must start the login. With no permitted role, it must show a "not permitted" page. */
        :>> title = "Route guards"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-223'> app223 {
        doc /* The loader of each list and detail route must load its data with queryClient.ensureQueryData and the query options of the entity slice. */
        :>> title = "Route loaders"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-224'> app224 {
        doc /* Each query key must be an array in the form [<entity>, <operation>, <parameters>]. */
        :>> title = "Query keys"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-225'> app225 {
        doc /* After a mutation, the generated code must invalidate the queries of the changed entity. */
        :>> title = "Query invalidation"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-226'> app226 {
        doc /* Each form must use TanStack Form with the Zod schema of its operation as the validator. Each field must use the shadcn/ui form components, with a label and an error message. */
        :>> title = "Forms"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-227'> app227 {
        doc /* The client must show a problem details response as an error message with its title and detail. */
        :>> title = "Error messages"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-228'> app228 {
        doc /* Each table must have column headers, and the user must be able to reach each control with the keyboard. */
        :>> title = "Accessibility"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-230'> app230 {
        doc /* Before the first render, the application must read /config.json. The file must give the API base URL, the AWS Region, the user pool ID, the app client ID and the managed login domain. */
        :>> title = "Runtime config file"; :>> kind = RequirementKind::interface; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-231'> app231 {
        doc /* shared/auth/amplify.gen.ts must configure Amplify Auth from the runtime configuration and use Cognito managed login with PKCE. */
        :>> title = "Amplify configuration"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-232'> app232 {
        doc /* The API client must add the access token of the session to each request as a bearer token. */
        :>> title = "Bearer token"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-233'> app233 {
        doc /* pnpm build must write the static files to dist/. The build must not contain environment values. */
        :>> title = "Static build"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-234'> app234 {
        doc /* The generator must write a Steiger configuration, and dsml check-output must run Steiger with no error. */
        :>> title = "Steiger check"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-APP-235'> app235 {
        doc /* The fixed-name generated files of the React target must be: package.json, tsconfig.json, vite.config.ts, index.html, components.json and steiger.config.ts. */
        :>> title = "React fixed names"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }

    // Next.js target (phase 3)
    #Requirement requirement <'PRD-APP-301'> app301 {
        doc /* The Next.js target must use strict TypeScript, pnpm, Next.js with the App Router, React, TanStack Query, TanStack Form, Zod, Tailwind CSS, shadcn/ui, Drizzle ORM and Amplify Auth with its Next.js adapter. The versions must come from the version baseline. */
        :>> title = "Next.js stack"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-302'> app302 {
        doc /* The Next.js app/ folder must be at the project root and hold only route files that re-export from src/. The generator must own the full app/ folder. */
        :>> title = "Route folder"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-303'> app303 {
        doc /* The FSD layers must be in src/, and the layers app and pages must have the names _app and _pages. */
        :>> title = "Renamed FSD layers"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-304'> app304 {
        doc /* The generator must map model elements to slices as PRD-APP-210 gives, with the layer names of PRD-APP-303. */
        :>> title = "Next.js FSD map"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-305'> app305 {
        doc /* A slice must export server-only modules through index.server.ts and other modules through index.ts. Each server-only module must import server-only. */
        :>> title = "Server public API"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-306'> app306 {
        doc /* The generated code must obey the FSD import rules of PRD-APP-203, and dsml check-output must run Steiger with no error. */
        :>> title = "Next.js FSD rules"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-APP-310'> app310 {
        doc /* For each operation, the generator must write a route handler in src/_app/api-routes/<operation>.gen.ts. A generated app/api/<path>/route.ts must re-export it. */
        :>> title = "Route handlers"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-311'> app311 {
        doc /* The REST contract must be the contract of the FastAPI target (PRD-APP-110 to PRD-APP-115), with the path prefix /api. */
        :>> title = "Same REST contract"; :>> kind = RequirementKind::interface; :>> priority = Priority::must; :>> status = Status::draft;
        frame oneModel;
    }
    #Requirement requirement <'PRD-APP-312'> app312 {
        doc /* A route handler must validate the input with the Zod schema of the operation, check the token and the roles, call the server function of the operation and return JSON or problem details. */
        :>> title = "Route handler steps"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-313'> app313 {
        doc /* For a CRUD operation, the generator must write the server function as features/<operation>/api/<operation>.server.gen.ts. For a custom operation, it must write <operation>.server.ts as a create-once stub that throws an error with the HTTP status 501. */
        :>> title = "Server functions"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-314'> app314 {
        doc /* Server components of pages must call the server functions for read and list directly, with no HTTP request. Client components must call the route handlers through TanStack Query. */
        :>> title = "Data paths"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-320'> app320 {
        doc /* For each view, the generator must write a page slice in src/_pages/<view> and a generated app/<route>/page.tsx that re-exports it. Routes must use the paths of PRD-APP-221. */
        :>> title = "Page slices"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-321'> app321 {
        doc /* Each form must be a client component that uses TanStack Form with the Zod schema of its operation. The route handler must validate the same input again with the same schema. */
        :>> title = "Two-sided validation"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-322'> app322 {
        doc /* Authentication must use Amplify Auth with its Next.js adapter, and the adapter must keep the tokens in cookies. */
        :>> title = "Cookie session"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-323'> app323 {
        doc /* The generated request interceptor (middleware.ts or proxy.ts, as the pinned Next.js version requires) must send a request for a protected page with no session to the login. */
        :>> title = "Request interceptor"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-324'> app324 {
        doc /* Server components and route handlers must get the session through the Amplify adapter and apply the role checks of PRD-APP-008. */
        :>> title = "Server session"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-325'> app325 {
        doc /* The root layout must give the public runtime values (Region, user pool ID, app client ID, login domain) to client components from server-side environment variables. The build must not use NEXT_PUBLIC_ variables. */
        :>> title = "Public runtime values"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-330'> app330 {
        doc /* The generator must write the Drizzle schema of all entities in src/shared/db/schema.gen.ts, with the type map of PRD-APP-121. */
        :>> title = "Drizzle schema"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-331'> app331 {
        doc /* The generator must write each migration from the difference between .dsml/schema-snapshot.json and the IR, in the file format that the Drizzle migrator reads. The project must not use drizzle-kit generate. */
        :>> title = "Drizzle migrations"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-332'> app332 {
        doc /* PRD-APP-125 to PRD-APP-128 must also apply to the Next.js target. The migration command must be node migrate.gen.mjs. */
        :>> title = "Next.js migration rules"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-333'> app333 {
        doc /* The Next.js build must use the standalone output. The Dockerfile must run the server on port 3000. */
        :>> title = "Next.js container"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-APP-334'> app334 {
        doc /* The fixed-name generated files of the Next.js target must be: package.json, tsconfig.json, next.config.ts, the full app/ folder, middleware.ts or proxy.ts, drizzle.config.ts, components.json, steiger.config.ts, Dockerfile and .dockerignore. */
        :>> title = "Next.js fixed names"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
}
