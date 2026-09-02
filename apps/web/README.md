# Web

Next.js 16 mobile-first PWA shell. Browser calls `/api/v1/*` on the same origin; Next.js rewrites those requests to the FastAPI service using `API_INTERNAL_URL`, allowing the API to set an HttpOnly session cookie on the web origin.

The OpenAPI schema is generated from FastAPI and then converted into TypeScript types. Do not hand-edit `src/lib/generated/api-schema.ts` once generated contracts are committed.
