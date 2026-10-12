import { createServerRunner } from "@aws-amplify/adapter-nextjs";

export const { runWithAmplifyServerContext } = createServerRunner({
  config: {
    Auth: {
      Cognito: {
        userPoolId: "eu-west-1_example",
        userPoolClientId: "example",
      },
    },
  },
});
