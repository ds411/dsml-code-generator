import { drizzle } from "drizzle-orm/node-postgres";
import { integer, pgTable, text, uuid } from "drizzle-orm/pg-core";
import { Pool } from "pg";
import { z } from "zod";

export const orderTable = pgTable("order", {
  id: uuid("id").primaryKey().defaultRandom(),
  name: text("name").notNull(),
  quantity: integer("quantity").notNull(),
});

export const orderInsertSchema = z.object({
  name: z.string().min(1),
  quantity: z.number().int().positive(),
});

export function createDatabase(connectionString: string) {
  return drizzle(new Pool({ connectionString }), { schema: { orderTable } });
}
