// The tests of the shared layer of the order portal (story #169). The CI
// job "React golden project" copies this folder into the copy of the
// golden project and runs Vitest. The tests replace fetch and the Amplify
// modules, thus they do not use the network.
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest } from "@/shared/api";
import { configureAuth, currentSession } from "@/shared/auth";
import { loadRuntimeConfig, runtimeConfig } from "@/shared/config";

const amplify = vi.hoisted(() => ({
  token: "the-access-token" as string | undefined,
  configure: vi.fn(),
}));

vi.mock("aws-amplify", () => ({ Amplify: { configure: amplify.configure } }));
vi.mock("aws-amplify/auth/enable-oauth-listener", () => ({}));
vi.mock("aws-amplify/auth", () => ({
  fetchAuthSession: () =>
    Promise.resolve({
      tokens:
        amplify.token === undefined
          ? undefined
          : {
              accessToken: {
                toString: () => amplify.token,
                payload: { "cognito:groups": ["clerk", 7] },
              },
            },
    }),
  signInWithRedirect: vi.fn(),
  signOut: vi.fn(),
}));

const config = {
  apiBaseUrl: "https://api.example.test/v1/",
  region: "eu-west-1",
  userPoolId: "eu-west-1_example",
  appClientId: "example-client",
  loginDomain: "example.auth.eu-west-1.amazoncognito.com",
};

interface Call {
  url: string;
  init: RequestInit | undefined;
}

const calls: Call[] = [];
let next: Response = new Response(null, { status: 204 });

function json(body: unknown, status = 200, type = "application/json") {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": type },
  });
}

vi.stubGlobal("fetch", (input: string | URL, init?: RequestInit) => {
  const url = input.toString();
  if (url === "/config.json") {
    return Promise.resolve(json(config));
  }
  calls.push({ url, init });
  return Promise.resolve(next);
});

beforeAll(async () => {
  await loadRuntimeConfig();
});

beforeEach(() => {
  calls.length = 0;
  amplify.token = "the-access-token";
  amplify.configure.mockClear();
});

describe("the runtime configuration", () => {
  it("comes from /config.json", () => {
    expect(runtimeConfig()).toEqual(config);
  });
});

describe("Amplify Auth", () => {
  it("uses Cognito managed login with the authorization code flow", () => {
    configureAuth(runtimeConfig(), "https://portal.example.test");
    expect(amplify.configure).toHaveBeenCalledWith({
      Auth: {
        Cognito: {
          userPoolId: "eu-west-1_example",
          userPoolClientId: "example-client",
          loginWith: {
            oauth: {
              domain: "example.auth.eu-west-1.amazoncognito.com",
              scopes: ["email", "openid", "profile"],
              redirectSignIn: ["https://portal.example.test/auth/callback"],
              redirectSignOut: ["https://portal.example.test/"],
              responseType: "code",
            },
          },
        },
      },
    });
  });

  it("gives the groups of the session", async () => {
    await expect(currentSession()).resolves.toEqual({
      accessToken: "the-access-token",
      groups: ["clerk"],
    });
  });
});

describe("the API client", () => {
  it("sends the access token as a bearer token", async () => {
    next = json({ id: "1" });
    const body = await apiRequest({
      method: "GET",
      path: "/orders",
      query: { limit: 50, offset: 0 },
    });
    expect(body).toEqual({ id: "1" });
    expect(calls).toHaveLength(1);
    const [call] = calls;
    expect(call?.url).toBe(
      "https://api.example.test/v1/orders?limit=50&offset=0",
    );
    const headers = new Headers(call?.init?.headers);
    expect(headers.get("Authorization")).toBe("Bearer the-access-token");
    expect(call?.init?.method).toBe("GET");
    expect(call?.init?.body).toBeNull();
  });

  it("sends no Authorization header with no session", async () => {
    amplify.token = undefined;
    next = new Response(null, { status: 204 });
    await expect(
      apiRequest({ method: "DELETE", path: "/orders/1" }),
    ).resolves.toBeUndefined();
    const headers = new Headers(calls[0]?.init?.headers);
    expect(headers.has("Authorization")).toBe(false);
  });

  it("sends the request body as JSON", async () => {
    next = json({ id: "2" }, 201);
    await apiRequest({ method: "POST", path: "/orders", body: { item: "A" } });
    const headers = new Headers(calls[0]?.init?.headers);
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(calls[0]?.init?.body).toBe('{"item":"A"}');
  });

  it("gives the title and the detail of a problem details response", async () => {
    next = json(
      {
        type: "about:blank",
        title: "Not Found",
        status: 404,
        detail: "The order 5 does not exist.",
      },
      404,
      "application/problem+json",
    );
    const error: unknown = await apiRequest({
      method: "GET",
      path: "/orders/5",
    }).catch((reason: unknown) => reason);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 404,
      title: "Not Found",
      detail: "The order 5 does not exist.",
      message: "Not Found: The order 5 does not exist.",
    });
  });

  it("gives the status of an error response with no problem details", async () => {
    next = new Response("Bad gateway", { status: 502 });
    await expect(
      apiRequest({ method: "GET", path: "/orders" }),
    ).rejects.toMatchObject({ status: 502, detail: undefined });
  });
});
