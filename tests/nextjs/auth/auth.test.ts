// The tests of the authentication of the order web (story #183). The CI
// job "Next.js golden project" copies this folder into the copy of the
// golden project and runs Vitest. The tests replace the Amplify adapter and
// give test tokens, thus they do not use the network.
import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { config, proxy } from "../../proxy";
import { checkAccess, loginUrl, returnPath, sessionOf } from "@/shared/auth";
import { authorize } from "@/shared/auth/index.server";

interface TestToken {
  payload: Record<string, unknown>;
  toString(): string;
}

const amplify = vi.hoisted(() => ({
  token: undefined as TestToken | undefined,
  contexts: [] as unknown[],
  sessionReads: 0,
}));

vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({ cookies: vi.fn() }));
vi.mock("@aws-amplify/adapter-nextjs", () => ({
  createServerRunner: () => ({
    runWithAmplifyServerContext: <Result>({
      nextServerContext,
      operation,
    }: {
      nextServerContext: unknown;
      operation: (contextSpec: unknown) => Promise<Result>;
    }) => {
      amplify.contexts.push(nextServerContext);
      return operation({});
    },
  }),
}));
vi.mock("aws-amplify/auth/server", () => ({
  fetchAuthSession: () => {
    amplify.sessionReads += 1;
    return Promise.resolve({
      tokens:
        amplify.token === undefined
          ? undefined
          : { accessToken: amplify.token },
    });
  },
}));

/** Make a test access token with the groups in the claim cognito:groups. */
function testToken(groups: unknown[]): TestToken {
  const payload = { sub: "test-user", "cognito:groups": groups };
  const part = (value: object) =>
    Buffer.from(JSON.stringify(value)).toString("base64url");
  const text = `${part({ alg: "none" })}.${part(payload)}.`;
  return { payload, toString: () => text };
}

const orders = { public: false, roles: ["admin", "clerk"] };
const cancelOrder = { public: false, roles: ["admin"] };

beforeEach(() => {
  vi.stubEnv("AWS_REGION", "eu-west-1");
  vi.stubEnv("COGNITO_USER_POOL_ID", "eu-west-1_example");
  vi.stubEnv("COGNITO_APP_CLIENT_ID", "example-client");
  vi.stubEnv("COGNITO_LOGIN_DOMAIN", "login.example.test");
  amplify.token = undefined;
  amplify.contexts.length = 0;
  amplify.sessionReads = 0;
});

describe("the role check", () => {
  it("permits a public item with no session", () => {
    expect(checkAccess(undefined, { public: true, roles: [] })).toBe(200);
  });

  it("gives 401 with no session", () => {
    expect(checkAccess(undefined, orders)).toBe(401);
  });

  it("gives 403 if no group is in the roles", () => {
    const session = sessionOf({ accessToken: testToken(["clerk"]) });
    expect(checkAccess(session, cancelOrder)).toBe(403);
  });

  it("permits a group that is in the roles", () => {
    const session = sessionOf({ accessToken: testToken(["clerk"]) });
    expect(checkAccess(session, orders)).toBe(200);
  });

  it("reads only the text groups of the token", () => {
    const token = testToken(["clerk", 7, null]);
    expect(sessionOf({ accessToken: token })).toEqual({
      accessToken: token.toString(),
      groups: ["clerk"],
    });
    expect(sessionOf({})).toBeUndefined();
    expect(sessionOf(undefined)).toBeUndefined();
  });
});

describe("the server helper authorize", () => {
  it("gives 401 with problem details if the request has no token", async () => {
    const result = await authorize(orders);
    expect(result.ok).toBe(false);
    if (result.ok) {
      return;
    }
    expect(result.response.status).toBe(401);
    expect(result.response.headers.get("Content-Type")).toBe(
      "application/problem+json",
    );
    expect(await result.response.json()).toEqual({
      type: "about:blank",
      title: "Unauthorized",
      status: 401,
      detail: "The request has no valid access token.",
    });
  });

  it("gives 403 with problem details if no group is in allowedRoles", async () => {
    amplify.token = testToken(["clerk"]);
    const result = await authorize(cancelOrder);
    expect(result.ok).toBe(false);
    if (result.ok) {
      return;
    }
    expect(result.response.status).toBe(403);
    expect(await result.response.json()).toEqual({
      type: "about:blank",
      title: "Forbidden",
      status: 403,
      detail: "The user has no role that the operation permits.",
    });
  });

  it("gives the session if a group is in allowedRoles", async () => {
    amplify.token = testToken(["admin"]);
    const result = await authorize(cancelOrder);
    expect(result).toEqual({
      ok: true,
      session: { accessToken: amplify.token.toString(), groups: ["admin"] },
    });
    expect(amplify.contexts).toHaveLength(1);
    expect(amplify.contexts[0]).toHaveProperty("cookies");
  });

  it("needs no token for a public item", async () => {
    const result = await authorize({ public: true, roles: [] });
    expect(result).toEqual({ ok: true, session: undefined });
    expect(amplify.sessionReads).toBe(0);
  });
});

describe("the request interceptor", () => {
  it("matches the pages of the views that need a session", () => {
    expect(config.matcher).toEqual(["/cancel-order", "/orders", "/orders/:id"]);
  });

  it("sends a request with no session to the login", async () => {
    const request = new NextRequest(
      "https://order-web.example.test/orders/7?page=2",
    );
    const response = await proxy(request);
    expect(response.status).toBe(307);
    const location = new URL(response.headers.get("Location") ?? "");
    expect(location.origin).toBe("https://order-web.example.test");
    expect(location.pathname).toBe("/auth/login");
    expect(location.searchParams.get("next")).toBe("/orders/7?page=2");
    expect(amplify.contexts[0]).toHaveProperty("request", request);
  });

  it("lets a request with a session go to the page", async () => {
    amplify.token = testToken(["clerk"]);
    const response = await proxy(
      new NextRequest("https://order-web.example.test/orders"),
    );
    expect(response.status).toBe(200);
    expect(response.headers.get("Location")).toBeNull();
    expect(response.headers.get("x-middleware-next")).toBe("1");
  });
});

describe("the login page path", () => {
  it("keeps the path after the login", () => {
    const url = loginUrl("/orders?page=2", "https://order-web.example.test/x");
    expect(url.toString()).toBe(
      "https://order-web.example.test/auth/login?next=%2Forders%3Fpage%3D2",
    );
  });

  it("permits only a path on this site", () => {
    expect(returnPath("/orders/7")).toBe("/orders/7");
    expect(returnPath(null)).toBe("/");
    expect(returnPath("https://other.example.test/")).toBe("/");
    expect(returnPath("//other.example.test/")).toBe("/");
    expect(returnPath("/\\other.example.test/")).toBe("/");
  });
});
