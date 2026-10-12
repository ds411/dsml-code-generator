// @vitest-environment jsdom
// The component tests of the pages layer and of the app layer of the order
// portal (story #174). The CI job "React golden project" copies this folder
// into the copy of the golden project and runs Vitest. The tests replace
// fetch and the Amplify modules, thus they do not use the network.
import { createMemoryHistory } from "@tanstack/react-router";
import { cleanup, render, screen, within } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import {
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import { AppProviders } from "@/app/providers/app-providers.gen";
import { createQueryClient } from "@/app/providers/query-client.gen";
import { startSession } from "@/app/providers/session.gen";
import { createAppRouter } from "@/app/router/router.gen";
import { listOrderQueryKey } from "@/entities/order";

/** The session of the tests: the groups of the user, or undefined for no session. */
const auth = vi.hoisted(() => ({
  groups: undefined as string[] | undefined,
  login: vi.fn(() => Promise.resolve()),
}));

vi.mock("aws-amplify", () => ({ Amplify: { configure: vi.fn() } }));
vi.mock("aws-amplify/auth/enable-oauth-listener", () => ({}));
vi.mock("aws-amplify/auth", () => ({
  fetchAuthSession: () =>
    Promise.resolve(
      auth.groups === undefined
        ? {}
        : {
            tokens: {
              accessToken: {
                toString: () => "the-access-token",
                payload: { "cognito:groups": auth.groups },
              },
            },
          },
    ),
  signInWithRedirect: auth.login,
  signOut: vi.fn(),
}));

const orders = [
  {
    id: "6f9619ff-8b86-4d01-b42d-000000000001",
    note: "Leave at the door.",
    status: "open",
    total: "1.50",
  },
  {
    id: "6f9619ff-8b86-4d01-b42d-000000000002",
    note: null,
    status: "shipped",
    total: "2.50",
  },
];

const urls: URL[] = [];

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

vi.stubGlobal("fetch", (input: string | URL) => {
  const text = input.toString();
  if (text === "/config.json") {
    return Promise.resolve(
      json({
        apiBaseUrl: "https://api.example.test",
        region: "eu-west-1",
        userPoolId: "eu-west-1_example",
        appClientId: "example-client",
        loginDomain: "example.auth.eu-west-1.amazoncognito.com",
      }),
    );
  }
  const url = new URL(text);
  urls.push(url);
  if (url.pathname === "/orders") {
    return Promise.resolve(json({ items: orders, total: orders.length }));
  }
  const found = orders.find((item) => url.pathname === `/orders/${item.id}`);
  return Promise.resolve(
    found === undefined
      ? json({ title: "Not Found", status: 404 }, 404)
      : json(found),
  );
});

/** Render the application at a path. */
function renderAt(path: string) {
  const queryClient = createQueryClient();
  const router = createAppRouter(
    queryClient,
    createMemoryHistory({ initialEntries: [path] }),
  );
  render(<AppProviders queryClient={queryClient} router={router} />);
  return { queryClient, router };
}

/** Give the texts of the links of the navigation. */
function navigationLinks(): (string | null)[] {
  const navigation = screen.getByRole("navigation", { name: "Main" });
  return within(navigation)
    .queryAllByRole("link")
    .map((item) => item.textContent);
}

beforeAll(async () => {
  // jsdom has no scrollTo. The router calls it after a navigation.
  window.scrollTo = vi.fn<typeof window.scrollTo>();
  await startSession();
});

beforeEach(() => {
  urls.length = 0;
  auth.groups = undefined;
  auth.login.mockClear();
});

afterEach(() => {
  cleanup();
});

describe("the check of the session and the roles of a route", () => {
  it("starts the login with no session", async () => {
    renderAt("/orders");
    expect(await screen.findByText("Wait for the login page.")).toBeDefined();
    expect(auth.login).toHaveBeenCalledOnce();
    expect(urls).toHaveLength(0);
    expect(screen.queryByRole("heading", { name: "Order list" })).toBeNull();
  });

  it("shows the not permitted page with no permitted role", async () => {
    auth.groups = ["clerk"];
    renderAt("/cancel-order");
    expect(
      await screen.findByRole("heading", { name: "Not permitted" }),
    ).toBeDefined();
    expect(auth.login).not.toHaveBeenCalled();
    expect(
      screen.queryByRole("heading", { name: "Cancel order form" }),
    ).toBeNull();
  });

  it("shows the page with a permitted role", async () => {
    auth.groups = ["admin"];
    renderAt("/cancel-order");
    expect(
      await screen.findByRole("heading", { name: "Cancel order form" }),
    ).toBeDefined();
    expect(screen.getByRole("button", { name: "Cancel order" })).toBeDefined();
  });

  it("shows the home page with no session", async () => {
    renderAt("/");
    expect(
      await screen.findByText("Log in to see the views of the application."),
    ).toBeDefined();
    expect(auth.login).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Log in" })).toBeDefined();
  });
});

describe("the loaders of the routes", () => {
  it("loads the list into the query cache before the page shows", async () => {
    auth.groups = ["clerk"];
    const { queryClient } = renderAt("/orders");
    expect(
      await screen.findByRole("heading", { name: "Order list" }),
    ).toBeDefined();
    expect(queryClient.getQueryData(listOrderQueryKey())).toBeDefined();
    expect(await screen.findByText("Leave at the door.")).toBeDefined();
    expect(urls.filter((url) => url.pathname === "/orders")).toHaveLength(1);
  });

  it("opens the details from the link of a row", async () => {
    auth.groups = ["clerk"];
    const user = userEvent.setup();
    renderAt("/orders");
    const links = await screen.findAllByRole("link", { name: "Details" });
    expect(links).toHaveLength(2);
    await user.click(links[1] as HTMLElement);
    expect(
      await screen.findByRole("heading", { name: "Order detail" }),
    ).toBeDefined();
    expect(await screen.findByText("shipped")).toBeDefined();
    expect(urls.at(-1)?.pathname).toBe(`/orders/${orders[1]?.id ?? ""}`);
  });
});

describe("the navigation", () => {
  it("shows the views of the navigation in the order of the model", async () => {
    auth.groups = ["clerk"];
    renderAt("/");
    expect(
      await screen.findByText("Select a view in the navigation."),
    ).toBeDefined();
    expect(navigationLinks()).toEqual(["Order list", "Place order form"]);
  });

  it("hides the views that the roles do not permit", async () => {
    auth.groups = ["viewer"];
    renderAt("/");
    expect(
      await screen.findByText("Select a view in the navigation."),
    ).toBeDefined();
    expect(navigationLinks()).toEqual([]);
  });

  it("shows no view with no session", async () => {
    renderAt("/");
    expect(
      await screen.findByText("Log in to see the views of the application."),
    ).toBeDefined();
    expect(navigationLinks()).toEqual([]);
  });
});
