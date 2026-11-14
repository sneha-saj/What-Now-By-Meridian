import { NextRequest } from "next/server";

// Forward only the headers the API needs. Modal adds internal request headers that
// another Modal endpoint rejects if a generic Next.js rewrite passes them through.
async function proxy(request: NextRequest): Promise<Response> {
  const base = process.env.API_URL ?? "http://localhost:8000";
  const path = request.nextUrl.pathname.slice("/api".length);
  const url = new URL(path + request.nextUrl.search, base);
  const headers = new Headers();
  for (const name of ["accept", "content-type", "x-access-code"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }

  const upstream = await fetch(url, {
    method: request.method,
    headers,
    body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer(),
    cache: "no-store",
  });
  const responseHeaders = new Headers();
  for (const name of ["content-type", "cache-control"]) {
    const value = upstream.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }
  return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
