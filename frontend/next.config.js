/** @type {import('next').NextConfig} */
const nextConfig = {
  // standalone only for Docker/self-hosted builds — not Vercel
  ...(process.env.BUILD_STANDALONE === "true" && { output: "standalone" }),
  turbopack: {
    root: __dirname,
  },
};

module.exports = nextConfig;
