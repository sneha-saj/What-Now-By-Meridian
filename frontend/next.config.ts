import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Keep `next build` from replacing files used by a running `next dev` server.
  distDir: process.env.NODE_ENV === "development" ? ".next-dev" : ".next",
};

export default nextConfig;
