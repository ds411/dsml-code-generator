// @vitest-environment jsdom
// The tests of the pages and the navigation of the order web (story #188).
// The CI job "Next.js golden project" copies this folder into the copy of
// the golden project and runs Vitest. The tests replace the Amplify adapter
// and the server functions, thus they use no network and no database.
// The pages check the session and the roles of the view (PRD-APP-009,
// PRD-APP-324). The list page and the detail page get the data from the
// server functions, with no HTTP request (PRD-APP-314).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Navigation } from "@/_app/layout/navigation.gen";
import { CancelOrderFormPage } from "@/_pages/cancel-order-form/index.server";
import { OrderDetailPage } from "@/_pages/order-detail/index.server";
import { OrderListPage } from "@/_pages/order-list/index.server";
import { sessionOf } from "@/shared/auth";

interface TestToken {
  payload: Record<string, unknown>;
  toString(): string;
}

/** Give an order with a key that ends with the number. */
function orderOf(index: number) {
  return {
    id: `6f9619ff-8b86-4d01-b42d-${String(index).padStart(12, "0")}`,
    note: index === 1 ? "Leave at the door." : null,
    status: "open",
    total: `${String(index)}.50`,
  };
}

const state = vi.hoisted(() => ({
  token: undefined as TestToken | undefined,
  calls: [] as string[],
}));

/** The error that replaces the redirect of Next.js. */
class RedirectError extends Error {
  constructor(readonly url: string) {
    super(`Redirect to ${url}`);
  }
}

vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({ cookies: vi.fn() }));
vi.mock("next/navigation", () => ({
  redirect: (url: string) => {
    throw new RedirectError(url);
  },
}));
vi.mock("@aws-amplify/adapter-nextjs", () => ({
  createServerRunner: () => ({
    runWithAmplifyServerContext: <Result,>({
      operation,
    }: {
      operation: (contextSpec: unknown) => Promise<Result>;
    }) => operation({}),
  }),
}));
vi.mock("aws-amplify/auth/server", () => ({
  fetchAuthSession: () =>
    Promise.resolve({
      tokens:
        state.token === undefined ? undefined : { accessToken: state.token },
    }),
}));
vi.mock("@/features/list-order/index.server", () => ({
  handleListOrder: (limit: number, offset: number) => {
    state.calls.push(`list ${String(limit)} ${String(offset)}`);
    const items = [orderOf(1), orderOf(2)];
    return Promise.resolve({ items, total: items.length });
  },
}));
vi.mock("@/features/read-order/index.server", () => ({
  handleReadOrder: (key: string) => {
    state.calls.push(`read ${key}`);
    return Promise.resolve({ ...orderOf(1), id: key });
  },
}));

/** Make a test access token with the groups in the claim cognito:groups. */
function testToken(groups: string[]): TestToken {
  const payload = { sub: "test-user", "cognito:groups": groups };
  return { payload, toString: () => "test-token" };
}

const requests: string[] = [];

vi.stubGlobal("fetch", (input: string | URL) => {
  requests.push(input.toString());
  return Promise.reject(new Error("The test permits no HTTP request."));
});

/** Render a page in the providers of TanStack Query. */
function renderPage(element: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 30_000 } },
  });
  return render(
    <QueryClientProvider client={client}>{element}</QueryClientProvider>,
  );
}

/** Give the redirect URL of a page, or undefined if the page did not redirect. */
async function redirectOf(page: Promise<unknown>): Promise<string | undefined> {
  try {
    await page;
  } catch (error) {
    if (error instanceof RedirectError) {
      return error.url;
    }
    throw error;
  }
  return undefined;
}

beforeEach(() => {
  vi.stubEnv("AWS_REGION", "eu-west-1");
  vi.stubEnv("COGNITO_USER_POOL_ID", "eu-west-1_example");
  vi.stubEnv("COGNITO_APP_CLIENT_ID", "example-client");
  vi.stubEnv("COGNITO_LOGIN_DOMAIN", "login.example.test");
  state.token = undefined;
  state.calls.length = 0;
  requests.length = 0;
});

afterEach(() => {
  cleanup();
});

describe("the page of the view orderList", () => {
  it("shows the orders of the server function with no HTTP request", async () => {
    state.token = testToken(["clerk"]);
    renderPage(await OrderListPage());
    expect(screen.getByRole("heading", { name: "Order list" })).toBeDefined();
    expect(await screen.findByText("Leave at the door.")).toBeDefined();
    expect(screen.getByText("Items 1 to 2 of 2")).toBeDefined();
    const links = screen.getAllByRole("link", { name: "Details" });
    expect(links.map((item) => item.getAttribute("href"))).toEqual([
      `/orders/${orderOf(1).id}`,
      `/orders/${orderOf(2).id}`,
    ]);
    expect(state.calls).toEqual(["list 50 0"]);
    expect(requests).toEqual([]);
  });

  it("shows the not permitted page with no permitted role", async () => {
    state.token = testToken(["viewer"]);
    renderPage(await OrderListPage());
    expect(
      screen.getByRole("heading", { name: "Not permitted" }),
    ).toBeDefined();
    expect(screen.queryByRole("table")).toBeNull();
    expect(state.calls).toEqual([]);
  });

  it("sends a user with no session to the login page", async () => {
    expect(await redirectOf(OrderListPage())).toBe(
      "/auth/login?next=%2Forders",
    );
    expect(state.calls).toEqual([]);
  });
});

describe("the page of the view orderDetail", () => {
  it("shows the order of the server function with no HTTP request", async () => {
    state.token = testToken(["admin"]);
    const id = orderOf(7).id;
    renderPage(await OrderDetailPage({ params: Promise.resolve({ id }) }));
    expect(screen.getByRole("heading", { name: "Order detail" })).toBeDefined();
    expect(await screen.findByText(id)).toBeDefined();
    expect(screen.getByText("Leave at the door.")).toBeDefined();
    expect(state.calls).toEqual([`read ${id}`]);
    expect(requests).toEqual([]);
  });

  it("sends a user with no session to the login page with the key", async () => {
    const id = orderOf(7).id;
    expect(
      await redirectOf(OrderDetailPage({ params: Promise.resolve({ id }) })),
    ).toBe(`/auth/login?next=%2Forders%2F${id}`);
  });
});

describe("the page of the view cancelOrderForm", () => {
  it("shows the form to a user with the role admin", async () => {
    state.token = testToken(["admin"]);
    renderPage(await CancelOrderFormPage());
    expect(
      screen.getByRole("heading", { name: "Cancel order form" }),
    ).toBeDefined();
    expect(screen.getByRole("button", { name: "Cancel order" })).toBeDefined();
  });

  it("shows the not permitted page to a user with only the role clerk", async () => {
    state.token = testToken(["clerk"]);
    renderPage(await CancelOrderFormPage());
    expect(
      screen.getByRole("heading", { name: "Not permitted" }),
    ).toBeDefined();
    expect(screen.queryByRole("button", { name: "Cancel order" })).toBeNull();
  });
});

describe("the navigation", () => {
  it("shows the views that the roles of the user permit", () => {
    const session = sessionOf({ accessToken: testToken(["clerk"]) });
    render(<Navigation session={session} />);
    const links = screen.getAllByRole("link");
    expect(links.map((item) => item.textContent)).toEqual(["Order list"]);
    expect(links[0]?.getAttribute("href")).toBe("/orders");
  });

  it("hides a view that the roles of the user do not permit", () => {
    const session = sessionOf({ accessToken: testToken(["viewer"]) });
    render(<Navigation session={session} />);
    expect(screen.getByRole("navigation", { name: "Main" })).toBeDefined();
    expect(screen.queryAllByRole("link")).toEqual([]);
  });

  it("hides each view that needs a session from a user with no session", () => {
    render(<Navigation session={undefined} />);
    expect(screen.queryAllByRole("link")).toEqual([]);
  });
});
