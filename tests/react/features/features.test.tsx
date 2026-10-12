// @vitest-environment jsdom
// The component tests of the features layer of the order portal (story
// #172). The CI job "React golden project" copies this folder into the copy
// of the golden project and runs Vitest. The tests replace fetch and the
// Amplify modules, thus they do not use the network.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  render,
  renderHook,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
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

import {
  CancelOrderForm,
  useCancelOrderMutation,
} from "@/features/cancel-order";
import {
  CreateOrderForm,
  useCreateOrderMutation,
} from "@/features/create-order";
import { PlaceOrderForm, usePlaceOrderMutation } from "@/features/place-order";
import { listOrderQueryKey, readOrderQueryKey } from "@/entities/order";
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

const ORDER_ID = "6f9619ff-8b86-4d01-b42d-00cf4fc964ff";

const order = {
  id: ORDER_ID,
  note: null,
  status: "open",
  total: "12.50",
};

interface Call {
  url: string;
  method: string | undefined;
  body: unknown;
}

const calls: Call[] = [];
let next: () => Response = () => json(order, 201);

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
  const url = input.toString();
  if (url === "/config.json") {
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
  const text = typeof init?.body === "string" ? init.body : undefined;
  calls.push({
    url,
    method: init?.method,
    body: text === undefined ? undefined : (JSON.parse(text) as unknown),
  });
  return Promise.resolve(next());
});

function newClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function wrapperOf(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  };
}

/** Give the shadcn/ui Field element of the control with the label. */
function fieldOf(label: string): HTMLElement {
  const field = screen
    .getByLabelText(label)
    .closest<HTMLElement>('[data-slot="field"]');
  if (field === null) {
    throw new Error(`The control "${label}" has no field.`);
  }
  return field;
}

function renderForm(element: ReactNode, client = newClient()) {
  return render(element, { wrapper: wrapperOf(client) });
}

beforeAll(async () => {
  await loadRuntimeConfig();
});

beforeEach(() => {
  calls.length = 0;
  next = () => json(order, 201);
});

afterEach(() => {
  cleanup();
});

describe("the form of the operation create", () => {
  it("shows a field error and sends no request", async () => {
    const user = userEvent.setup();
    renderForm(<CreateOrderForm />);
    await user.type(screen.getByLabelText("Total"), "12.12345");
    await user.click(screen.getByRole("button", { name: "Create" }));
    const field = fieldOf("Total");
    expect(await within(field).findByRole("alert")).toHaveProperty(
      "textContent",
      "The value must be a decimal number with no more than 14 digits before the decimal point and 4 digits after it.",
    );
    expect(screen.getByLabelText("Total").getAttribute("aria-invalid")).toBe(
      "true",
    );
    expect(calls).toHaveLength(0);
  });

  it("shows the field error of a required field", async () => {
    const user = userEvent.setup();
    renderForm(<CreateOrderForm />);
    await user.click(screen.getByRole("button", { name: "Create" }));
    const field = fieldOf("Total");
    expect(await within(field).findByRole("alert")).toBeDefined();
    const note = fieldOf("Note");
    expect(within(note).queryByRole("alert")).toBeNull();
    expect(calls).toHaveLength(0);
  });

  it("shows the title and the detail of a problem details response", async () => {
    next = () =>
      problem(422, "Unprocessable Content", "The total is too high.");
    const user = userEvent.setup();
    renderForm(<CreateOrderForm />);
    await user.type(screen.getByLabelText("Total"), "12.50");
    await user.click(screen.getByRole("button", { name: "Create" }));
    expect(await screen.findByText("Unprocessable Content")).toBeDefined();
    expect(screen.getByText("The total is too high.")).toBeDefined();
    expect(calls).toHaveLength(1);
  });

  it("sends the values and gives the new entity", async () => {
    const onSuccess = vi.fn();
    const user = userEvent.setup();
    renderForm(<CreateOrderForm onSuccess={onSuccess} />);
    await user.type(screen.getByLabelText("Note"), "Leave at the door.");
    await user.selectOptions(screen.getByLabelText("Status"), "shipped");
    await user.type(screen.getByLabelText("Total"), "12.50");
    await user.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalledWith(order);
    });
    expect(calls).toEqual([
      {
        url: "https://api.example.test/orders",
        method: "POST",
        body: { note: "Leave at the door.", status: "shipped", total: "12.50" },
      },
    ]);
  });

  it("does not send an empty optional field", async () => {
    const user = userEvent.setup();
    renderForm(<CreateOrderForm defaultValues={{ total: "3" }} />);
    await user.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => {
      expect(calls).toHaveLength(1);
    });
    expect(calls[0]?.body).toEqual({ status: "open", total: "3" });
  });

  it("lets the user reach each control with the keyboard", async () => {
    const user = userEvent.setup();
    renderForm(<CreateOrderForm />);
    await user.tab();
    expect(document.activeElement).toBe(screen.getByLabelText("Note"));
    await user.tab();
    expect(document.activeElement).toBe(screen.getByLabelText("Status"));
    await user.tab();
    expect(document.activeElement).toBe(screen.getByLabelText("Total"));
    await user.keyboard("7");
    await user.tab();
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: "Create" }),
    );
    await user.keyboard("{Enter}");
    await waitFor(() => {
      expect(calls).toHaveLength(1);
    });
  });
});

describe("the forms of the custom operations", () => {
  it("sends the request body of placeOrder", async () => {
    const onSuccess = vi.fn();
    const user = userEvent.setup();
    renderForm(<PlaceOrderForm onSuccess={onSuccess} />);
    await user.type(screen.getByLabelText("Total"), "99.5");
    await user.click(screen.getByRole("button", { name: "Place order" }));
    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalledWith(order);
    });
    expect(calls).toEqual([
      {
        url: "https://api.example.test/orders/place",
        method: "POST",
        body: { total: "99.5" },
      },
    ]);
  });

  it("shows a field error of placeOrder", async () => {
    const user = userEvent.setup();
    renderForm(<PlaceOrderForm />);
    await user.type(screen.getByLabelText("Total"), "1e2");
    await user.click(screen.getByRole("button", { name: "Place order" }));
    const field = fieldOf("Total");
    expect(await within(field).findByRole("alert")).toHaveProperty(
      "textContent",
      "The value must be a decimal number.",
    );
    expect(calls).toHaveLength(0);
  });

  it("puts the parameter of cancelOrder in the path", async () => {
    next = () => json({ ...order, status: "cancelled" });
    const user = userEvent.setup();
    renderForm(<CancelOrderForm defaultValues={{ order_id: ORDER_ID }} />);
    await user.click(screen.getByRole("button", { name: "Cancel order" }));
    await waitFor(() => {
      expect(calls).toHaveLength(1);
    });
    expect(calls[0]).toEqual({
      url: `https://api.example.test/orders/${ORDER_ID}/cancel`,
      method: "POST",
      body: undefined,
    });
  });

  it("shows a problem details response of cancelOrder", async () => {
    next = () => problem(409, "Conflict", "The order is already shipped.");
    const user = userEvent.setup();
    renderForm(<CancelOrderForm />);
    await user.type(screen.getByLabelText("Order id"), ORDER_ID);
    await user.click(screen.getByRole("button", { name: "Cancel order" }));
    const alert = await screen.findByText("Conflict");
    expect(alert).toBeDefined();
    expect(screen.getByText("The order is already shipped.")).toBeDefined();
  });
});

describe("the mutations", () => {
  function seed(client: QueryClient) {
    client.setQueryData(listOrderQueryKey(), { items: [order], total: 1 });
    client.setQueryData(readOrderQueryKey(ORDER_ID), order);
  }

  function invalidated(client: QueryClient): boolean[] {
    return [listOrderQueryKey(), readOrderQueryKey(ORDER_ID)].map(
      (key) => client.getQueryState(key)?.isInvalidated ?? false,
    );
  }

  it("invalidate the queries of the entity after create", async () => {
    const client = newClient();
    seed(client);
    const { result } = renderHook(() => useCreateOrderMutation(), {
      wrapper: wrapperOf(client),
    });
    expect(invalidated(client)).toEqual([false, false]);
    await result.current.mutateAsync({ status: "open", total: 5 });
    expect(invalidated(client)).toEqual([true, true]);
  });

  it("invalidate the queries of the entity after a custom operation", async () => {
    const client = newClient();
    seed(client);
    const { result } = renderHook(() => usePlaceOrderMutation(), {
      wrapper: wrapperOf(client),
    });
    await result.current.mutateAsync({ total: "5" });
    expect(invalidated(client)).toEqual([true, true]);
  });

  it("do not invalidate the queries after an error", async () => {
    next = () => problem(404, "Not Found", "The order does not exist.");
    const client = newClient();
    seed(client);
    const { result } = renderHook(() => useCancelOrderMutation(), {
      wrapper: wrapperOf(client),
    });
    await expect(
      result.current.mutateAsync({ order_id: ORDER_ID }),
    ).rejects.toMatchObject({ status: 404, title: "Not Found" });
    expect(invalidated(client)).toEqual([false, false]);
  });
});
