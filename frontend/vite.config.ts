import { defineConfig, loadEnv } from "vite";
import type { Plugin } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const pkg = JSON.parse(readFileSync(fileURLToPath(new URL("./package.json", import.meta.url)), "utf-8")) as {
  version: string;
};

function devWebappRedirectPlugin(): Plugin {
  return {
    name: "dev-webapp-redirect",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = req.url?.split("?")[0] ?? "";
        if (url === "/" || url === "/api/webapp" || url === "/api/webapp/") {
          res.statusCode = 302;
          res.setHeader("Location", "/webapp/");
          res.end();
          return;
        }
        next();
      });
    },
  };
}

const SHELL_DYNAMIC_ENTRY = /\/src\/locales\/[^/]+\.json$|\/workbox-window\//;

function appShellPlugin(shellFiles: Set<string>): Plugin {
  return {
    name: "pwa-app-shell",
    apply: "build",
    generateBundle(_options, bundle) {
      shellFiles.clear();
      const visit = (fileName: string) => {
        const chunk = bundle[fileName];
        if (!chunk || shellFiles.has(fileName)) return;
        shellFiles.add(fileName);
        if (chunk.type !== "chunk") return;
        chunk.imports.forEach(visit);
        chunk.viteMetadata?.importedCss.forEach(visit);
        chunk.viteMetadata?.importedAssets.forEach(visit);
      };
      for (const chunk of Object.values(bundle)) {
        if (chunk.type !== "chunk") continue;
        const facade = chunk.facadeModuleId?.replace(/\\/g, "/") ?? "";
        if (chunk.isEntry || (chunk.isDynamicEntry && SHELL_DYNAMIC_ENTRY.test(facade))) {
          visit(chunk.fileName);
        }
      }
    },
  };
}

export default defineConfig(({ mode }) => {
  const shellFiles = new Set<string>();
  const env = loadEnv(mode, process.cwd(), "");
  const apiProxyTarget = env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8001";

  return {
    plugins: [
      devWebappRedirectPlugin(),
      react(),
      appShellPlugin(shellFiles),
      VitePWA({
        registerType: "autoUpdate",
        injectRegister: "auto",
        base: "/webapp/",
        // The manifest and icons are served dynamically by the backend (admin-
        // editable name/description/icon), not generated statically here.
        manifest: false,
        includeAssets: ["icons/icon-192.png", "icons/icon-512.png", "icons/icon-maskable-192.png", "icons/icon-maskable-512.png"],
        workbox: {
          globPatterns: ["**/*.{js,css,html,ico,png,svg,woff2}"],
          manifestTransforms: [
            async (entries) => ({
              manifest:
                shellFiles.size === 0
                  ? entries
                  : entries.filter((e) => !e.url.startsWith("assets/") || shellFiles.has(e.url)),
              warnings: [],
            }),
          ],
          navigateFallback: "/webapp/index.html",
          navigateFallbackDenylist: [/^\/api\//],
          runtimeCaching: [
            {
              // Always try the live manifest/icons first so an admin's edit
              // shows up immediately; fall back to cache only when offline.
              // Served from /api/webapp/... — see pwaBranding.ts for why.
              urlPattern: /\/api\/webapp\/(manifest\.webmanifest|icons\/.*)/,
              handler: "NetworkFirst",
              options: { cacheName: "pwa-branding" },
            },
            {
              urlPattern: /\/webapp\/assets\//,
              handler: "CacheFirst",
              options: {
                cacheName: "webapp-assets",
                expiration: { maxEntries: 150, maxAgeSeconds: 30 * 24 * 60 * 60 },
              },
            },
          ],
        },
        devOptions: {
          enabled: false,
        },
      }),
    ],
    base: "/webapp/",
    define: {
      __APP_VERSION__: JSON.stringify(pkg.version),
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (/node_modules\/(react|react-dom|scheduler)\//.test(id)) {
              return "react-vendor";
            }
          },
        },
      },
    },
    server: {
      port: 5174,
      proxy: {
        "/api": {
          target: apiProxyTarget,
          changeOrigin: true,
          secure: false,
        },
      },
    },
  };
});
