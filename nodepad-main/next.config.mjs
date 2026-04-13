import { dirname, join } from "path"
import { fileURLToPath } from "url"

const __dirname = dirname(fileURLToPath(import.meta.url))

/** @type {import('next').NextConfig} */
function supabaseConnectOrigins() {
  const raw = process.env.NEXT_PUBLIC_SUPABASE_URL || ""
  if (!raw.trim()) {
    // Before .env is filled; broad fallback so local templates do not hard-fail CSP.
    return ["https://*.supabase.co", "wss://*.supabase.co"]
  }
  try {
    const u = new URL(raw)
    const https = u.origin
    const wss = u.protocol === "https:" ? `wss://${u.host}` : ""
    return wss ? [https, wss] : [https]
  } catch {
    return ["https://*.supabase.co", "wss://*.supabase.co"]
  }
}

function contentSecurityPolicyValue() {
  const connectParts = [
    "'self'",
    ...supabaseConnectOrigins(),
    "https://openrouter.ai",
    "https://api.openai.com",
    "https://api.z.ai",
    "https://cloud.umami.is",
    "https://api-gateway.umami.dev",
  ]
  return [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cloud.umami.is",
    "style-src 'self' 'unsafe-inline'",
    `connect-src ${connectParts.join(" ")}`,
    "img-src 'self' data: blob: https://i.ytimg.com",
    "font-src 'self' data:",
    "frame-src https://www.youtube-nocookie.com https://www.youtube.com",
    "frame-ancestors 'none'",
  ].join("; ")
}

const nextConfig = {
  // Pin Turbopack root when a parent directory has another package-lock.json (e.g. ~/package-lock.json).
  // resolveAlias: if the repo root has a package.json, CSS/PostCSS may resolve bare imports from that
  // directory (no node_modules there) and fail on tw-animate-css — map to this app's node_modules.
  turbopack: {
    root: __dirname,
    resolveAlias: {
      "tw-animate-css": join(__dirname, "node_modules/tw-animate-css"),
    },
  },
  typescript: {
    // Build errors are intentionally ignored — see CLAUDE.md
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  webpack(config) {
    config.resolve.alias = {
      ...config.resolve.alias,
      "tw-animate-css": join(__dirname, "node_modules/tw-animate-css"),
    }
    return config
  },
  async headers() {
    return [
      {
        // Apply security headers to every route
        source: "/(.*)",
        headers: [
          {
            // Prevent framing (clickjacking)
            key: "X-Frame-Options",
            value: "DENY",
          },
          {
            // Stop MIME-type sniffing
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            // Limit referrer info sent to third-party origins
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            // Permissions policy — disable features the app doesn't use
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
          {
            // Content Security Policy
            // - default-src self: everything defaults to same-origin
            // - script-src: Next.js needs 'unsafe-inline' + 'unsafe-eval' in dev;
            //   nonces are the proper fix but require custom server — this is the
            //   pragmatic baseline for a static/Vercel deployment.
            // - connect-src: Supabase https + wss derived from NEXT_PUBLIC_SUPABASE_URL
            // - img-src: data URIs for inline images, blob for canvas exports
            // - style-src unsafe-inline: Tailwind injects inline styles at runtime
            key: "Content-Security-Policy",
            value: contentSecurityPolicyValue(),
          },
        ],
      },
    ]
  },
}

export default nextConfig
