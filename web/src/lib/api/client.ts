// The typed API client. Server-only: it holds API_URL and the viewer's credentials (a session token, or the
// development "View as" id). Importing this from a Client Component fails the build.
import "server-only";

import { redirect } from "next/navigation";
import createClient, { type Middleware } from "openapi-fetch";

import type { paths } from "./schema";

/** Any 401 means the session ended (expired, idle, signed out elsewhere, deactivated): go sign in again. */
const signInOn401: Middleware = {
  onResponse({ response }) {
    if (response.status === 401) redirect("/sign-in?expired=1");
  },
};

/**
 * A client that calls FastAPI as the signed-in person. Paths, params and responses are all checked against
 * schema.d.ts, generated from the API's OpenAPI schema (`npm run gen:api`).
 */
export function apiWithSession(token: string) {
  const client = createClient<paths>({ baseUrl: process.env.API_URL, headers: { Authorization: `Bearer ${token}` } });
  client.use(signInOn401);
  return client;
}

/** Development and the public demo only: act as a chosen person (the API ignores this header elsewhere). */
export function apiAs(viewerId: string) {
  const client = createClient<paths>({ baseUrl: process.env.API_URL, headers: { "X-Dev-User": viewerId } });
  client.use(signInOn401);
  return client;
}

/** No viewer: signing in, one-time links, and the development "View as" list. */
export function publicApi() {
  return createClient<paths>({ baseUrl: process.env.API_URL });
}
