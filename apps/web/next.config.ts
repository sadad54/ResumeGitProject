import type { NextConfig } from "next";

// API origin the CSP's connect-src must allow — same value the client fetch
// helper (src/lib/api.ts) uses, kept in sync via the same env var rather than
// hardcoded, so a deployed API origin doesn't silently break under CSP.
const apiOrigin = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

// Next.js injects inline bootstrap/hydration scripts it does not currently
// expose a nonce for in this version, so script-src needs 'unsafe-inline' —
// documented here as a known, deliberate relaxation rather than a silent gap.
// Everything else is locked to 'self'; no third-party script/style/frame
// origins are permitted at all.
//
// Dev-only additions (never shipped to production, verified by NODE_ENV):
// - 'unsafe-eval': Next/React's dev-mode Fast Refresh uses eval() to
//   reconstruct stack traces across module boundaries. Production builds
//   never call eval() (React logs this itself) — this is a real, narrow
//   dev-tooling need, not a general relaxation.
// - ws://localhost:*: the Turbopack dev server's HMR socket. CSP's 'self'
//   does not cover a ws:// connection from an http:// page — the scheme
//   differs, so it needs its own explicit allowance in connect-src.
const isDev = process.env.NODE_ENV !== "production";
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:",
  "font-src 'self'",
  `connect-src 'self' ${apiOrigin}${isDev ? " ws://localhost:*" : ""}`,
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Standalone output: .next/standalone is a self-contained server that runs
  // with plain `node`, so the production image (infra/docker/Dockerfile.web)
  // ships no npm at all. See that file for why that matters.
  output: "standalone",
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
