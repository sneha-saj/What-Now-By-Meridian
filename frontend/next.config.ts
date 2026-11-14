import type { NextConfig } from "next";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

// Proxy /api/* to the FastAPI backend so the browser never deals with CORS.
const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/:path*` }];
  },
};

export default nextConfig;
