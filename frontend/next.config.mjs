/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:7070/api/:path*',
      },
    ];
  },
};

export default nextConfig;
