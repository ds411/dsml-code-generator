// @vitest-environment jsdom
// The component tests of the feature slices of the order web (story #184).
// The CI job "Next.js golden project" copies this folder into the copy of
// the golden project and runs Vitest. The tests replace fetch, thus they do
// not use the network. The forms are client components that send each
// request to a route handler under /api on the same origin (PRD-APP-311,
// PRD-APP-321). The browser sends the session cookies, thus a request has
// no bearer token (PRD-APP-322).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CancelOrderForm } from "@/features/cancel-order";
import { CreateOrderForm } from "@/features/create-order";
import { DeleteOrderButton } from "@/features/delete-order";
import { orderQueryKey } from "@/entities/order";

const ORDER_ID = "6f9619ff-8b86-4d01-b42d-00cf4fc964ff";

const order = {
  id: ORDER_ID,
  note: null,
  status: "cancelled",
  total: "12.50",
};

interface Call {
  url: string;
  method: string | undefined;
  authorization: string | null;
  credentials: RequestCredentials | undefined;
  body: unknown;
}

const calls: Call[] = [];
let next: () => Response = () => json(order);

function json(body: unknown, status = 200, type = "application/json") {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": type },
  });
}

function problem(status: number, title: string, detail: string) {
  return json(
    { type: "about:blank", title, status, detail },
    status,
    "application/problem+json",
  );
}

vi.stubGlobal("fetch", (input: string | URL, init?: RequestInit) => {
  const text = typeof init?.body === "string" ? init.body : undefined;
  calls.push({
    url: input.toString(),
    method: init?.method,
    authorization: new Headers(init?.headers).get("Authorization"),
    credentials: init?.credentials,
    body: text === undefined ? undefined : (JSON.parse(text) as unknown),
  });
  return Promise.resolve(next());
});

function newClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function renderWith(element: ReactNode, client = newClient()) {
  return render(
    <QueryClientProvider client={client}>{element}</QueryClientProvider>,
  );
}

beforeEach(() => {
  calls.length = 0;
  next = () => json(order);
});

afterEach(() => {
  cleanup();
});

describe("the form of the operation cancelOrder", () => {
  it("sends the request to the route handler and gives the order", async () => {
    const onSuccess = vi.fn();
    const user = userEvent.setup();
    renderWith(<CancelOrderForm onSuccess={onSuccess} />);
    await user.type(screen.getByLabelText("Order id"), ORDER_ID);
    await user.click(screen.getByRole("button", { name: "Cancel order" }));
    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalledWith(order);
    });
    expect(calls).toEqual([
      {
        url: `/api/orders/${ORDER_ID}/cancel`,
        method: "POST",
        authorization: null,
        credentials: "same-origin",
        body: undefined,
      },
    ]);
  });

  it("shows a field error and sends no request", async () => {
    const user = userEvent.setup();
    renderWith(<CancelOrderForm />);
    await user.type(screen.getByLabelText("Order id"), "not-a-uuid");
    await user.click(screen.getByRole("button", { name: "Cancel order" }));
    const field = screen
      .getByLabelText("Order id")
      .closest<HTMLElement>('[data-slot="field"]');
    expect(field).not.toBeNull();
    if (field !== null) {
      expect(await within(field).findByRole("alert")).toBeDefined();
    }
    expect(calls).toHaveLength(0);
  });

  it("shows the title and the detail of a problem details response", async () => {
    next = () =>
      problem(403, "Forbidden", "The roles of the user do not permit it.");
    const user = userEvent.setup();
    renderWith(<CancelOrderForm />);
    await user.type(screen.getByLabelText("Order id"), ORDER_ID);
    await user.click(screen.getByRole("button", { name: "Cancel order" }));
    expect(await screen.findByText("Forbidden")).toBeDefined();
    expect(
      screen.getByText("The roles of the user do not permit it."),
    ).toBeDefined();
  });
});

describe("the mutations of the CRUD operations", () => {
  it("sends the values of the form of create to /api/orders", async () => {
    const onSuccess = vi.fn();
    next = () => json({ ...order, status: "open" }, 201);
    const user = userEvent.setup();
    renderWith(<CreateOrderForm onSuccess={onSuccess} />);
    await user.type(screen.getByLabelText("Total"), "12.50");
    await user.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalled();
    });
    expect(calls).toEqual([
      {
        url: "/api/orders",
        method: "POST",
        authorization: null,
        credentials: "same-origin",
        body: { status: "open", total: "12.50" },
      },
    ]);
  });

  it("deletes an order and invalidates the queries of the entity", async () => {
    next = () => new Response(null, { status: 204 });
    const client = newClient();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    const user = userEvent.setup();
    renderWith(<DeleteOrderButton id={ORDER_ID} />, client);
    await user.click(screen.getByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));
    await waitFor(() => {
      expect(invalidate).toHaveBeenCalledWith({ queryKey: orderQueryKey });
    });
    expect(calls.map((call) => [call.method, call.url])).toEqual([
      ["DELETE", `/api/orders/${ORDER_ID}`],
    ]);
  });
});
