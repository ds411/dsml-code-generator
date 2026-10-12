import { getTableName } from "drizzle-orm";
import { describe, expect, it } from "vitest";
import { orderInsertSchema, orderTable } from "./schema";

describe("orderTable", () => {
  it("has the table name order", () => {
    expect(getTableName(orderTable)).toBe("order");
  });

  it("rejects an empty name", () => {
    expect(orderInsertSchema.safeParse({ name: "", quantity: 1 }).success).toBe(
      false,
    );
  });
});
