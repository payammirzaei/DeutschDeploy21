import createClient from "openapi-fetch";
import type { paths } from "./generated/api-schema";

type ApiResult = {
  // Bootstrap OpenAPI schema is untyped (`paths = any`).
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data?: any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  error?: any;
  response: Response;
};

type ApiCall = (url: string, init?: object) => Promise<ApiResult>;

// Default missing init so local typecheck works before CI regenerates types.
// credentials: include keeps the HttpOnly session cookie on LAN / IP hosts.
// eslint-disable-next-line @typescript-eslint/no-explicit-any -- openapi-fetch client until schema is typed
const client = createClient<paths>({ baseUrl: "", credentials: "include" }) as any;

export const api = {
  GET: ((url: string, init?: object) => client.GET(url, init ?? {})) as ApiCall,
  POST: ((url: string, init?: object) => client.POST(url, init ?? {})) as ApiCall,
  PUT: ((url: string, init?: object) => client.PUT(url, init ?? {})) as ApiCall,
  PATCH: ((url: string, init?: object) => client.PATCH(url, init ?? {})) as ApiCall,
  DELETE: ((url: string, init?: object) => client.DELETE(url, init ?? {})) as ApiCall,
};
