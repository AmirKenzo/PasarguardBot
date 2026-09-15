import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import fa from "./locales/fa.json";
import en from "./locales/en.json";

const savedLanguage = localStorage.getItem("language") || "fa";

const resources = {
  fa: { translation: fa },
  en: { translation: en },
};

i18n.use(initReactI18next).init({
  resources,
  lng: savedLanguage,
  fallbackLng: "fa",
  ns: ["translation"],
  defaultNS: "translation",
  interpolation: { escapeValue: false },
  react: {
    useSuspense: false,
  },
});

export default i18n;
