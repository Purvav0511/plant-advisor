import type { NextConfig } from "next";

// Static export (SPEC §14): no server at runtime. Detail pages use query strings (decision 0014).
const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
};

export default nextConfig;
