import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import fa from "./locales/fa.json";
import en from "./locales/en.json";

const resources = { fa, en };

const savedLanguage = localStorage.getItem("language") || "fa";

i18n.use(initReactI18next).init({
  resources,
  lng: savedLanguage,
  fallbackLng: "fa",
  interpolation: { escapeValue: false },
});

export default i18n;
