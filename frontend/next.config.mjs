/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // The agent improvement report is generated synchronously by calling an LLM,
  // which regularly takes 40–90s. Next.js's default dev-proxy timeout is 30s,
  // which causes the frontend fetch to fail with a 500 even though the backend
  // eventually returns a valid response. Raise the proxy timeout to 5 minutes
  // so long-running endpoints (report generation, bulk evaluations) don't get
  // cut off at the proxy layer.
  experimental: {
    proxyTimeout: 300_000, // 5 minutes
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.BACKEND_URL || 'http://localhost:4040'}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
