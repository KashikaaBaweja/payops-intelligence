/** @type {import('next').NextConfig} */
const apiProxy = process.env.PAYOPS_API_PROXY || "http://127.0.0.1:8000";

const nextConfig = {
  output: "standalone",
  allowedDevOrigins: ["localhost", "127.0.0.1", "192.0.0.2"],
  async rewrites() {
    return [{ source: "/backend/:path*", destination: `${apiProxy}/:path*` }];
  },
};

module.exports = nextConfig;
