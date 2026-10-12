// A stand-in for the public API of the segment shared/api. The CI job
// "React golden project" copies this file into the copy of the golden
// project only if the golden project has no file src/shared/api/index.ts.
// The shared layer story (#169) writes the real API client. It must give
// the same function apiRequest with the same types.

/** One request to the API that the application calls. */
export interface ApiRequest {
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  /** The path of the operation, after the API base URL. */
  path: string;
  /** The query parameters. */
  query?: Readonly<Record<string, string | number | boolean>>;
  /** The request body. The client sends it as JSON. */
  body?: unknown;
  signal?: AbortSignal;
}

/**
 * Send a request to the API and give the JSON body of the response. A
 * response with no body gives `undefined`.
 */
export function apiRequest(request: ApiRequest): Promise<unknown> {
  return Promise.reject(
    new Error(
      `The stand-in client cannot send ${request.method} ${request.path}.`,
    ),
  );
}
