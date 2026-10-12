import { z } from "zod";

export const orderSchema = z.object({
  name: z.string().min(1),
  quantity: z.number().int().positive(),
});

export type Order = z.infer<typeof orderSchema>;

export function parseOrder(value: unknown): Order {
  return orderSchema.parse(value);
}

export async function fetchOrders(): Promise<Order[]> {
  const response = await fetch("/api/orders");
  const body: unknown = await response.json();
  return z.array(orderSchema).parse(body);
}
