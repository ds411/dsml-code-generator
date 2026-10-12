import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { Amplify } from "aws-amplify";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { router } from "./router";
import "./styles.css";

Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId: "eu-west-1_example",
      userPoolClientId: "example",
    },
  },
});

const queryClient = new QueryClient();
const root = document.getElementById("root");

if (root !== null) {
  createRoot(root).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </StrictMode>,
  );
}
