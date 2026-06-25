/** @type {import('next').NextConfig} */
const apiOrigin = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const nextConfig = {
  reactStrictMode: true,
  // Proxy chart PNGs + JSON API through Next.js so /pairs works without a separate .env
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${apiOrigin}/api/:path*` },
    ];
  },
};

export default nextConfig;
