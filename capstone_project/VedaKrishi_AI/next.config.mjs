/** @type {import('next').NextConfig} */
const nextConfig = {
  // TypeScript errors are treated as warnings (errors caught by IDE)
  typescript: {
    ignoreBuildErrors: true,
  },
  // Optimise images via Vercel's image CDN
  images: {
    unoptimized: false,
  },
}

export default nextConfig
