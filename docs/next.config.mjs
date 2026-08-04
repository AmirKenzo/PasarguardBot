import { createMDX } from 'fumadocs-mdx/next';

const withMDX = createMDX();

const repo = 'PasarguardBot';
const isGithubPages = process.env.GITHUB_PAGES === 'true';
const basePath = isGithubPages ? `/${repo}` : '';

/** @type {import('next').NextConfig} */
const config = {
  output: 'export',
  reactStrictMode: true,
  trailingSlash: true,
  images: {
    unoptimized: true,
  },
  basePath: basePath || undefined,
  assetPrefix: basePath ? `${basePath}/` : undefined,
  env: {
    NEXT_PUBLIC_BASE_PATH: basePath,
  },
  // Avoid broken client/HMR when opening via 127.0.0.1 instead of localhost
  allowedDevOrigins: ['127.0.0.1', 'localhost'],
  // TypeScript 7 has no JS compiler API; use project-local `tsc` for typecheck.
  experimental: {
    useTypeScriptCli: true,
  },
};

export default withMDX(config);
