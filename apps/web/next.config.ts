import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // CI performs a strict TypeScript check after regenerating the API client from
  // FastAPI. Deployment builders may not have that generated contract available,
  // so Next's redundant build-time type check is disabled here.
  typescript: {
    ignoreBuildErrors: true,
  },
};

export default nextConfig;
