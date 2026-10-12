import { describe, expect, it } from "vitest";
import { parseOrder } from "./order";

describe("parseOrder", () => {
  it("accepts a valid order", () => {
    expect(parseOrder({ name: "A", quantity: 2 })).toEqual({
      name: "A",
      quantity: 2,
    });
  });

  it("rejects a quantity of zero", () => {
    expect(() => parseOrder({ name: "A", quantity: 0 })).toThrow();
  });
});
