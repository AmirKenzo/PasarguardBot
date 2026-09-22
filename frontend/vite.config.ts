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

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiProxyTarget = env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8001";

  return {
    plugins: [
      devWebappRedirectPlugin(),
      react(),
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
