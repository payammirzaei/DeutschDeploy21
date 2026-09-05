# Web

Next.js 16 mobile-first PWA shell. Browser calls `/api/v1/*` on the same origin; Next.js rewrites those requests to the FastAPI service using `API_INTERNAL_URL`, allowing the API to set an HttpOnly session cookie on the web origin.

The OpenAPI schema is generated from FastAPI and then converted into TypeScript types. Do not hand-edit `src/lib/generated/api-schema.ts` once generated contracts are committed.

## Toolchain

Use Node 22 and npm 10.9.x from the repository root:

```bash
npm ci
npm run lint
npm run typecheck
npm test
npm run build
```

`package-lock.json` is the source of truth. Prefer `npm ci` over `npm install` after a clean checkout. `npm install` is not required and can still hit npm 10.9's arborist crash on Vitest 4 optional peers (`Cannot read properties of null (reading 'edgesOut')`).

`.npmrc` sets `legacy-peer-deps=true` so `npm ci` stays reproducible without changing package versions. The lockfile was generated with npm 10.9.x; keep npm on 10.9.x (`packageManager` in the root `package.json`).

`npm run typecheck` must work without first regenerating OpenAPI. The web client defaults missing `openapi-fetch` init objects so the committed bootstrap schema (`paths = any`) type-checks. CI still exports FastAPI OpenAPI and runs `npm run api:generate` before typecheck.
