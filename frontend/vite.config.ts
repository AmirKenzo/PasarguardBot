import { defineConfig, loadEnv } from "vite";
import type { Plugin } from "vite";
import react from "@vitejs/plugin-react";

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
    plugins: [devWebappRedirectPlugin(), react()],
    base: "/webapp/",
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
