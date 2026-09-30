import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Next locks its output folder per running server, so the Playwright server (e2e/) builds into its own
  // folder and can run beside `npm run dev`.
  distDir: process.env.NEXT_DIST_DIR || ".next",
};

export default nextConfig;
