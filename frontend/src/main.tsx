import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { LazyMotion } from "framer-motion";
import { HashRouter } from "react-router-dom";
import { ToastProvider } from "./components/ui/Toast";
import { ThemeProvider } from "./design/ThemeProvider";
import { LanguageProvider } from "./context/LanguageContext";
import { captureTelegramInitData } from "./telegramInit";
import { AuthProvider } from "./context/AuthContext";
import App from "./App";
import { applyPwaBranding } from "./pwaBranding";
import { i18nReady } from "./i18n";
import "./index.css";

const loadMotionFeatures = () => import("./lib/motionFeatures").then((mod) => mod.default);

captureTelegramInitData();
void applyPwaBranding();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

void i18nReady.then(() =>
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <LazyMotion features={loadMotionFeatures} strict>
        <ThemeProvider>
          <LanguageProvider>
            <QueryClientProvider client={queryClient}>
              <ToastProvider>
                <HashRouter>
                  <AuthProvider>
                    <App />
                  </AuthProvider>
                </HashRouter>
              </ToastProvider>
            </QueryClientProvider>
          </LanguageProvider>
        </ThemeProvider>
      </LazyMotion>
    </React.StrictMode>,
  ),
);
