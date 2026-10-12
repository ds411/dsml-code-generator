// The HTTP tests of the route handlers of the order web (story #186). The
// CI job "Next.js golden project" copies this folder into the copy of the
// golden project and runs Vitest with a PostgreSQL service container. The
// environment variables DATABASE_* give the database. The tests apply the
// migrations, replace the Amplify adapter with test tokens and send requests
// to the route handlers of app/api/. They do not use the network.
import { drizzle } from "drizzle-orm/node-postgres";
import { migrate } from "drizzle-orm/node-postgres/migrator";
import { Pool } from "pg";
import {
  afterAll,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import * as cancelRoute from "../../app/api/orders/[id]/cancel/route";
import * as entityRoute from "../../app/api/orders/[id]/route";
import * as ordersRoute from "../../app/api/orders/route";
import * as healthRoute from "../../app/healthz/route";
import { readDatabaseConfig } from "@/shared/db/index.server";

interface TestToken {
  payload: Record<string, unknown>;
  toString(): string;
}

const amplify = vi.hoisted(() => ({
  token: undefined as TestToken | undefined,
}));

vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({ cookies: vi.fn() }));
vi.mock("@aws-amplify/adapter-nextjs", () => ({
  createServerRunner: () => ({
    runWithAmplifyServerContext: <Result>({
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
        amplify.token === undefined
          ? undefined
          : { accessToken: amplify.token },
    }),
}));

/** Give the requests a test access token with the groups in the claim cognito:groups. */
function login(...groups: string[]): void {
  const payload = { sub: "test-user", "cognito:groups": groups };
  const part = (value: object) =>
    Buffer.from(JSON.stringify(value)).toString("base64url");
  const text = `${part({ alg: "none" })}.${part(payload)}.`;
  amplify.token = { payload, toString: () => text };
}

/** The route handler of one method of one route file. */
type Handler<Params> = (
  request: Request,
  context: { params: Promise<Params> },
) => Promise<Response>;

/** Send a request to a route handler with the path parameters of the route. */
function send<Params extends object>(
  handler: Handler<Params>,
  method: string,
  path: string,
  options: { body?: unknown; text?: string; params?: Params } = {},
): Promise<Response> {
  const text =
    options.text ??
    (options.body === undefined ? undefined : JSON.stringify(options.body));
  const request = new Request(`http://localhost${path}`, {
    method,
    headers: text === undefined ? {} : { "Content-Type": "application/json" },
    body: text,
  });
  const params = options.params ?? ({} as Params);
  return handler(request, { params: Promise.resolve(params) });
}

/** The fields of an order in a response. */
interface Order {
  id: string;
  note: string | null;
  status: string;
  total: string;
}

const MISSING = "00000000-0000-4000-8000-000000000000";

const pool = new Pool(readDatabaseConfig());

/** Add an order through the route handler and give it. */
async function createOrder(body: object = {}): Promise<Order> {
  const response = await send(ordersRoute.POST, "POST", "/api/orders", {
    body: { status: "open", total: "12.5", note: null, ...body },
  });
  expect(response.status).toBe(201);
  return (await response.json()) as Order;
}

/** Examine a problem details response and give its body. */
async function problem(
  response: Response,
  status: number,
): Promise<Record<string, unknown>> {
  expect(response.status).toBe(status);
  expect(response.headers.get("Content-Type")).toBe("application/problem+json");
  const body = (await response.json()) as Record<string, unknown>;
  expect(body.status).toBe(status);
  return body;
}

beforeAll(async () => {
  vi.stubEnv("AWS_REGION", "eu-west-1");
  vi.stubEnv("COGNITO_USER_POOL_ID", "eu-west-1_example");
  vi.stubEnv("COGNITO_APP_CLIENT_ID", "example-client");
  vi.stubEnv("COGNITO_LOGIN_DOMAIN", "login.example.test");
  await migrate(drizzle({ client: pool }), { migrationsFolder: "migrations" });
});

beforeEach(async () => {
  await pool.query('TRUNCATE TABLE "order"');
  login("clerk");
});

afterAll(async () => {
  await pool.end();
});

describe("the CRUD operations", () => {
  it("create gives 201 with the entity and a new key", async () => {
    const order = await createOrder({ note: "First", total: 7 });
    expect(order).toEqual({
      id: expect.stringMatching(/^[0-9a-f-]{36}$/) as unknown,
      note: "First",
      status: "open",
      total: "7.0000",
    });
  });

  it("read gives 200 with the entity", async () => {
    const order = await createOrder();
    const response = await send(
      entityRoute.GET,
      "GET",
      `/api/orders/${order.id}`,
      {
        params: { id: order.id },
      },
    );
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(order);
  });

  it("update gives 200 and changes only the fields of the body", async () => {
    const order = await createOrder({ note: "Old" });
    const response = await send(
      entityRoute.PATCH,
      "PATCH",
      `/api/orders/${order.id}`,
      {
        body: { status: "shipped" },
        params: { id: order.id },
      },
    );
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ ...order, status: "shipped" });
    const empty = await send(
      entityRoute.PATCH,
      "PATCH",
      `/api/orders/${order.id}`,
      {
        body: {},
        params: { id: order.id },
      },
    );
    expect(empty.status).toBe(200);
    expect(await empty.json()).toEqual({ ...order, status: "shipped" });
  });

  it("update can set a nullable field to null", async () => {
    const order = await createOrder({ note: "Old" });
    const response = await send(
      entityRoute.PATCH,
      "PATCH",
      `/api/orders/${order.id}`,
      {
        body: { note: null },
        params: { id: order.id },
      },
    );
    expect(await response.json()).toEqual({ ...order, note: null });
  });

  it("delete gives 204 with no body and deletes the entity", async () => {
    const order = await createOrder();
    const response = await send(
      entityRoute.DELETE,
      "DELETE",
      `/api/orders/${order.id}`,
      {
        params: { id: order.id },
      },
    );
    expect(response.status).toBe(204);
    expect(await response.text()).toBe("");
    const read = await send(entityRoute.GET, "GET", `/api/orders/${order.id}`, {
      params: { id: order.id },
    });
    expect(read.status).toBe(404);
  });

  it("list gives 200 with the items sorted by key and the number of all entities", async () => {
    const orders = await Promise.all([1, 2, 3].map(() => createOrder()));
    const keys = orders.map((order) => order.id).sort();
    const all = await send(ordersRoute.GET, "GET", "/api/orders");
    expect(all.status).toBe(200);
    const page = (await all.json()) as { items: Order[]; total: number };
    expect(page.total).toBe(3);
    expect(page.items.map((order) => order.id)).toEqual(keys);
    const part = await send(
      ordersRoute.GET,
      "GET",
      "/api/orders?limit=1&offset=1",
    );
    expect(await part.json()).toEqual({
      items: [expect.objectContaining({ id: keys[1] }) as unknown],
      total: 3,
    });
  });
});

describe("the error responses", () => {
  it("give 401 with no token", async () => {
    amplify.token = undefined;
    const body = await problem(
      await send(ordersRoute.GET, "GET", "/api/orders"),
      401,
    );
    expect(body.title).toBe("Unauthorized");
  });

  it("give 403 if no group of the user is in the roles", async () => {
    login("guest");
    await problem(await send(ordersRoute.GET, "GET", "/api/orders"), 403);
    login("clerk");
    const order = await createOrder();
    const body = await problem(
      await send(cancelRoute.POST, "POST", `/api/orders/${order.id}/cancel`, {
        params: { id: order.id },
      }),
      403,
    );
    expect(body.title).toBe("Forbidden");
  });

  it("give 404 for an entity that does not exist", async () => {
    const path = `/api/orders/${MISSING}`;
    const params = { id: MISSING };
    for (const response of [
      await send(entityRoute.GET, "GET", path, { params }),
      await send(entityRoute.PATCH, "PATCH", path, {
        body: { status: "shipped" },
        params,
      }),
      await send(entityRoute.DELETE, "DELETE", path, { params }),
    ]) {
      const body = await problem(response, 404);
      expect(body.detail).toBe("No entity Order has this key.");
    }
  });

  it("give 409 for a value that breaks a unique rule", async () => {
    await pool.query('CREATE UNIQUE INDEX test_order_note ON "order" (note)');
    try {
      const order = await createOrder({ note: "Same" });
      const create = await send(ordersRoute.POST, "POST", "/api/orders", {
        body: { status: "open", total: 1, note: "Same" },
      });
      await problem(create, 409);
      const other = await createOrder({ note: "Other" });
      const update = await send(
        entityRoute.PATCH,
        "PATCH",
        `/api/orders/${other.id}`,
        {
          body: { note: order.note },
          params: { id: other.id },
        },
      );
      await problem(update, 409);
    } finally {
      await pool.query("DROP INDEX test_order_note");
    }
  });

  it("give 422 for a body that breaks a field rule", async () => {
    const negative = await send(ordersRoute.POST, "POST", "/api/orders", {
      body: { status: "open", total: -1 },
    });
    const body = await problem(negative, 422);
    expect(body.errors).toEqual([
      expect.objectContaining({ location: ["body", "total"] }) as unknown,
    ]);
    const long = await send(ordersRoute.POST, "POST", "/api/orders", {
      body: { status: "open", total: 1, note: "x".repeat(501) },
    });
    await problem(long, 422);
    const status = await send(ordersRoute.POST, "POST", "/api/orders", {
      body: { status: "lost", total: 1 },
    });
    await problem(status, 422);
    const json = await send(ordersRoute.POST, "POST", "/api/orders", {
      text: "{",
    });
    await problem(json, 422);
    const order = await createOrder();
    const key = await send(
      entityRoute.PATCH,
      "PATCH",
      `/api/orders/${order.id}`,
      {
        body: { id: MISSING },
        params: { id: order.id },
      },
    );
    await problem(key, 422);
  });

  it("give 422 for a path or a query parameter that is not correct", async () => {
    const key = await send(entityRoute.GET, "GET", "/api/orders/7", {
      params: { id: "7" },
    });
    const body = await problem(key, 422);
    expect(body.errors).toEqual([
      expect.objectContaining({ location: ["path", "id"] }) as unknown,
    ]);
    for (const query of ["limit=0", "limit=201", "limit=a", "offset=-1"]) {
      await problem(
        await send(ordersRoute.GET, "GET", `/api/orders?${query}`),
        422,
      );
    }
  });

  it("give 501 for a custom operation with no logic", async () => {
    login("admin");
    const order = await createOrder();
    const body = await problem(
      await send(cancelRoute.POST, "POST", `/api/orders/${order.id}/cancel`, {
        params: { id: order.id },
      }),
      501,
    );
    expect(body).toEqual({
      type: "about:blank",
      title: "Not Implemented",
      status: 501,
      detail: "Write the logic of the operation cancelOrder.",
    });
    const key = await send(cancelRoute.POST, "POST", "/api/orders/7/cancel", {
      params: { id: "7" },
    });
    await problem(key, 422);
  });
});

describe("GET /healthz", () => {
  it("gives 200 with no token", async () => {
    amplify.token = undefined;
    const response = await send(healthRoute.GET, "GET", "/healthz");
    expect(response.status).toBe(200);
  });
});
