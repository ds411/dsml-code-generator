// @vitest-environment jsdom
// The component tests of the widgets layer of the order portal (story
// #173). The CI job "React golden project" copies this folder into the copy
// of the golden project and runs Vitest. The tests replace fetch and the
// Amplify modules, thus they do not use the network.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { type ReactNode } from "react";
import {
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import { OrderDetails } from "@/widgets/order-details";
import { OrderTable } from "@/widgets/order-list";
import { loadRuntimeConfig } from "@/shared/config";

vi.mock("aws-amplify", () => ({ Amplify: { configure: vi.fn() } }));
vi.mock("aws-amplify/auth/enable-oauth-listener", () => ({}));
vi.mock("aws-amplify/auth", () => ({
  fetchAuthSession: () =>
    Promise.resolve({
      tokens: {
        accessToken: {
          toString: () => "the-access-token",
          payload: { "cognito:groups": ["clerk"] },
        },
      },
    }),
  signInWithRedirect: vi.fn(),
  signOut: vi.fn(),
}));

/** Give an order with a key that ends with the number. */
function orderOf(index: number) {
  return {
    id: `6f9619ff-8b86-4d01-b42d-${String(index).padStart(12, "0")}`,
    note: index === 1 ? "Leave at the door." : null,
    status: "open",
    total: `${String(index)}.50`,
  };
}

const orders = Array.from({ length: 5 }, (_, index) => orderOf(index + 1));

const urls: URL[] = [];
let failure: Response | undefined;

function json(body: unknown, status = 200, type = "application/json") {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": type },
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
  if (failure !== undefined) {
    return Promise.resolve(failure);
  }
  if (url.pathname === "/orders") {
    const limit = Number(url.searchParams.get("limit"));
    const offset = Number(url.searchParams.get("offset"));
    return Promise.resolve(
      json({ items: orders.slice(offset, offset + limit), total: 5 }),
    );
  }
  const found = orders.find((item) => url.pathname === `/orders/${item.id}`);
  return Promise.resolve(
    found === undefined
      ? json({ title: "Not Found", status: 404 }, 404)
      : json(found),
  );
});

function renderWidget(element: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>{element}</QueryClientProvider>,
  );
}

beforeAll(async () => {
  await loadRuntimeConfig();
});

beforeEach(() => {
  urls.length = 0;
  failure = undefined;
});

afterEach(() => {
  cleanup();
});

describe("the table of the entity Order", () => {
  it("shows a header for each column", async () => {
    renderWidget(<OrderTable />);
    expect(await screen.findByText("Leave at the door.")).toBeDefined();
    const headers = screen
      .getAllByRole("columnheader")
      .map((item) => item.textContent);
    expect(headers).toEqual(["Id", "Note", "Status", "Total"]);
    expect(screen.getAllByRole("row")).toHaveLength(6);
    expect(screen.getByText("Items 1 to 5 of 5")).toBeDefined();
    expect(urls[0]?.searchParams.get("limit")).toBe("50");
    expect(urls[0]?.searchParams.get("offset")).toBe("0");
  });

  it("shows the next page and the previous page", async () => {
    const user = userEvent.setup();
    renderWidget(<OrderTable pageSize={2} />);
    expect(await screen.findByText("Items 1 to 2 of 5")).toBeDefined();
    const previous = screen.getByRole("button", { name: "Previous page" });
    const next = screen.getByRole("button", { name: "Next page" });
    expect(previous).toHaveProperty("disabled", true);
    await user.click(next);
    expect(await screen.findByText("Items 3 to 4 of 5")).toBeDefined();
    expect(screen.getByText(orders[2]?.id ?? "")).toBeDefined();
    expect(urls.at(-1)?.searchParams.get("limit")).toBe("2");
    expect(urls.at(-1)?.searchParams.get("offset")).toBe("2");
    await user.click(next);
    expect(await screen.findByText("Items 5 to 5 of 5")).toBeDefined();
    expect(next).toHaveProperty("disabled", true);
    await user.click(previous);
    expect(await screen.findByText("Items 3 to 4 of 5")).toBeDefined();
  });

  it("lets the user change the page with the keyboard", async () => {
    const user = userEvent.setup();
    renderWidget(<OrderTable pageSize={2} />);
    expect(await screen.findByText("Items 1 to 2 of 5")).toBeDefined();
    await user.tab();
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: "Next page" }),
    );
    await user.keyboard("{Enter}");
    expect(await screen.findByText("Items 3 to 4 of 5")).toBeDefined();
    await user.tab({ shift: true });
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: "Previous page" }),
    );
  });

  it("shows the controls of each row in the column Actions", async () => {
    renderWidget(
      <OrderTable
        actions={(item) => <a href={`/orders/${item.id}`}>Open</a>}
      />,
    );
    expect(await screen.findAllByRole("link", { name: "Open" })).toHaveLength(
      5,
    );
    expect(screen.getByRole("columnheader", { name: "Actions" })).toBeDefined();
  });

  it("shows the title and the detail of a problem details response", async () => {
    failure = json(
      {
        type: "about:blank",
        title: "Forbidden",
        status: 403,
        detail: "The role is not permitted.",
      },
      403,
      "application/problem+json",
    );
    renderWidget(<OrderTable />);
    expect(await screen.findByText("Forbidden")).toBeDefined();
    expect(screen.getByText("The role is not permitted.")).toBeDefined();
  });
});

describe("the details of the entity Order", () => {
  it("shows each field of the entity", async () => {
    const order = orders[0];
    if (order === undefined) {
      throw new Error("The test has no order.");
    }
    renderWidget(<OrderDetails id={order.id} />);
    const list = (await screen.findByText(order.id)).closest("dl");
    if (list === null) {
      throw new Error("The details have no description list.");
    }
    const terms = within(list)
      .getAllByRole("term")
      .map((item) => item.textContent);
    expect(terms).toEqual(["Id", "Note", "Status", "Total"]);
    expect(within(list).getByText("Leave at the door.")).toBeDefined();
    expect(within(list).getByText("1.50")).toBeDefined();
    expect(urls.at(-1)?.pathname).toBe(`/orders/${order.id}`);
  });
});
