// @vitest-environment jsdom
// The component tests of the widget slices of the order web (story #184).
// The CI job "Next.js golden project" copies this folder into the copy of
// the golden project and runs Vitest. The tests replace fetch, thus they do
// not use the network. The widgets are client components that read the
// data from the route handlers under /api through TanStack Query
// (PRD-APP-314).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OrderDetails } from "@/widgets/order-details";
import { OrderTable } from "@/widgets/order-list";

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

const requests: string[] = [];
let failure: Response | undefined;

function json(body: unknown, status = 200, type = "application/json") {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": type },
  });
}

vi.stubGlobal("fetch", (input: string | URL) => {
  const text = input.toString();
  requests.push(text);
  if (failure !== undefined) {
    return Promise.resolve(failure);
  }
  const url = new URL(text, "http://localhost");
  if (url.pathname === "/api/orders") {
    const limit = Number(url.searchParams.get("limit"));
    const offset = Number(url.searchParams.get("offset"));
    return Promise.resolve(
      json({ items: orders.slice(offset, offset + limit), total: 5 }),
    );
  }
  const found = orders.find(
    (item) => url.pathname === `/api/orders/${item.id}`,
  );
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

beforeEach(() => {
  requests.length = 0;
  failure = undefined;
});

afterEach(() => {
  cleanup();
});

describe("the table of the entity Order", () => {
  it("reads the first page from the route handler", async () => {
    renderWidget(<OrderTable />);
    expect(await screen.findByText("Leave at the door.")).toBeDefined();
    const headers = screen
      .getAllByRole("columnheader")
      .map((item) => item.textContent);
    expect(headers).toEqual(["Id", "Note", "Status", "Total"]);
    expect(screen.getByText("Items 1 to 5 of 5")).toBeDefined();
    expect(requests).toEqual(["/api/orders?limit=50&offset=0"]);
  });

  it("shows the next page", async () => {
    const user = userEvent.setup();
    renderWidget(<OrderTable pageSize={2} />);
    expect(await screen.findByText("Items 1 to 2 of 5")).toBeDefined();
    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(await screen.findByText("Items 3 to 4 of 5")).toBeDefined();
    expect(requests).toEqual([
      "/api/orders?limit=2&offset=0",
      "/api/orders?limit=2&offset=2",
    ]);
  });

  it("shows the title and the detail of a problem details response", async () => {
    failure = json(
      {
        type: "about:blank",
        title: "Unauthorized",
        status: 401,
        detail: "The request has no valid token.",
      },
      401,
      "application/problem+json",
    );
    renderWidget(<OrderTable />);
    expect(await screen.findByText("Unauthorized")).toBeDefined();
    expect(screen.getByText("The request has no valid token.")).toBeDefined();
  });
});

describe("the details of the entity Order", () => {
  it("reads one order from the route handler", async () => {
    const order = orders[0];
    if (order === undefined) {
      throw new Error("The test has no order.");
    }
    renderWidget(<OrderDetails id={order.id} />);
    expect(await screen.findByText("Leave at the door.")).toBeDefined();
    expect(screen.getByText(order.total)).toBeDefined();
    expect(requests).toEqual([`/api/orders/${order.id}`]);
  });
});
