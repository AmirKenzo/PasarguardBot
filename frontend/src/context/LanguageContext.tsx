import { createContext, useContext, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

interface LanguageContextType {
  language: string;
  setLanguage: (lang: string) => void;
  direction: "rtl" | "ltr";
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const { i18n } = useTranslation();
  const [language, setLanguageState] = useState(i18n.language || "fa");
  const direction = language === "fa" ? "rtl" : "ltr";

  const setLanguage = async (lang: string) => {
    await i18n.changeLanguage(lang);
    setLanguageState(lang);
    localStorage.setItem("language", lang);
    document.documentElement.dir = lang === "fa" ? "rtl" : "ltr";
    document.documentElement.lang = lang;
  };

  useEffect(() => {
    const currentLang = i18n.language || "fa";
    setLanguageState(currentLang);
    document.documentElement.dir = currentLang === "fa" ? "rtl" : "ltr";
    document.documentElement.lang = currentLang;
  }, [i18n.language, i18n]);

  return (
    <LanguageContext.Provider value={{ language, setLanguage, direction }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useLanguage must be used within LanguageProvider");
  }
  return context;
}
