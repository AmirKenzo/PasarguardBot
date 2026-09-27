import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { HashRouter } from "react-router-dom";
import { ToastProvider } from "./components/ui/Toast";
import { ThemeProvider } from "./design/ThemeProvider";
import { LanguageProvider } from "./context/LanguageContext";
import { captureTelegramInitData } from "./telegramInit";
import { AuthProvider } from "./context/AuthContext";
import App from "./App";
import { applyPwaBranding } from "./pwaBranding";
import "./i18n";
import "./index.css";

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

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
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
  </React.StrictMode>,
);
