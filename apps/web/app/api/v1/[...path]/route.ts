import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "content-length",
  "host",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const apiInternalUrl = process.env.API_INTERNAL_URL ?? "http://localhost:8000";
  const { path } = await context.params;
  const incomingUrl = new URL(request.url);
  const target = new URL(`/api/v1/${path.map(encodeURIComponent).join("/")}`, apiInternalUrl);
  target.search = incomingUrl.search;

  const requestHeaders = new Headers(request.headers);
  for (const header of HOP_BY_HOP_HEADERS) requestHeaders.delete(header);

  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  const upstream = await fetch(target, {
    method: request.method,
    headers: requestHeaders,
    body: hasBody ? await request.arrayBuffer() : undefined,
    redirect: "manual",
    cache: "no-store",
  });

  const responseHeaders = new Headers(upstream.headers);
  for (const header of HOP_BY_HOP_HEADERS) responseHeaders.delete(header);

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;
export const HEAD = proxy;
