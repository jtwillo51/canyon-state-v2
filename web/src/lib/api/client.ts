// The typed API client. Server-only: it holds API_URL and, until real sign-in, the dev viewer header.
// Importing this from a Client Component fails the build.
import "server-only";

import createClient from "openapi-fetch";

import type { paths } from "./schema";

/**
 * A client that calls FastAPI as `viewerId`. Paths, params and responses are all checked against
 * schema.d.ts, generated from the API's OpenAPI schema (`npm run gen:api`).
 *
 * Until Stage 3 sign-in, the viewer travels in the development-only X-Dev-User header.
 */
export function apiAs(viewerId: string) {
  return createClient<paths>({
    baseUrl: process.env.API_URL,
    headers: { "X-Dev-User": viewerId },
  });
}

/** A client with no viewer, for the development "View as" user list. */
export function devApi() {
  return createClient<paths>({ baseUrl: process.env.API_URL });
}
