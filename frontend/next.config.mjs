/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: 'lh3.googleusercontent.com' },
    ],
  },
  async rewrites() {
    const apiBaseUrl =
      process.env['NEXT_PUBLIC_API_BASE_URL'] ?? 'http://localhost:17004';
    return [
      {
        source: '/api/v1/:path*',
        destination: `${apiBaseUrl}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
