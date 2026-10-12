// The server function of the operation cancelOrder: POST /orders/{orderId}/cancel.
//
// Write the logic of the operation in this file. The generator wrote this
// file one time, and it does not change it again. The route handler in
// src/_app/api-routes/cancel-order.gen.ts validates the input and checks the
// roles. Then it calls handleCancelOrder with the input and the session of
// the user. Get the database with getDatabase() of @/shared/db/index.server.
// Throw a ProblemError to return an API error, for example HTTP 404.
//
// If the operation changes in the model, the generator changes the schemas.
// Then a type check shows each place where this file does not agree with
// the schemas. Until you write the logic, the route handler returns HTTP 501.
import "server-only";

import type { Session } from "@/shared/auth";
import { ProblemError } from "@/shared/http/index.server";

import type { CancelOrderInput, CancelOrderOutput } from "./cancel-order.gen";

/** The detail of the response HTTP 501. */
const NOT_IMPLEMENTED = "Write the logic of the operation cancelOrder.";

/** The type of the server function. The route handler calls it with these parameters. */
type Handler = (
  input: CancelOrderInput,
  session: Session | undefined,
) => Promise<CancelOrderOutput>;

// trace: OrderWeb::CancelOrder
/** Do the operation CancelOrder. Replace this body with the logic. */
export const handleCancelOrder: Handler = () =>
  Promise.reject(new ProblemError(501, NOT_IMPLEMENTED));
