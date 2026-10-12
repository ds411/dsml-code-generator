// The Zod schemas of the order portal must accept and refuse the same test
// values as the Pydantic models of the called FastAPI application
// (PRD-APP-211). The CI job "React golden project" copies this folder into
// the copy of the golden project and runs Vitest. The Python test
// tests/test_react_entities.py gives the same values to the Pydantic models.
import { describe, expect, it } from "vitest";

import * as order from "@/entities/order";

import data from "./order-portal.json";

interface Case {
  schema: string;
  rule: string;
  valid: boolean;
  value: unknown;
}

const schemas: Record<
  string,
  { safeParse: (value: unknown) => { success: boolean } }
> = {
  createOrderInputSchema: order.createOrderInputSchema,
  orderSchema: order.orderSchema,
};

describe("the field rules of the order portal", () => {
  it.each(data.cases as Case[])(
    "$schema: $rule (valid: $valid)",
    ({ schema, valid, value }) => {
      const found = schemas[schema];
      expect(found, `The schema ${schema} is not in the test.`).toBeDefined();
      expect(found?.safeParse(value).success).toBe(valid);
    },
  );
});
