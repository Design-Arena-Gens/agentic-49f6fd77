/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  eslint: {
    ignoreDuringBuilds: true
  },
  experimental: {
    serverActions: {
      bodySizeLimit: '4mb'
    }
  },
  env: {
    AGENT_API_BASE_URL: process.env.AGENT_API_BASE_URL,
    GEMINI_MODEL: process.env.GEMINI_MODEL || 'gemini-1.5-flash'
  }
};

export default nextConfig;
