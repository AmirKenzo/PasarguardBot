import i18n from "i18next";
import { initReactI18next } from "react-i18next";

export const SUPPORTED_LANGUAGES = ["fa", "en"] as const;
export type Language = (typeof SUPPORTED_LANGUAGES)[number];

const loaders: Record<Language, () => Promise<{ default: Record<string, unknown> }>> = {
  fa: () => import("./locales/fa.json"),
  en: () => import("./locales/en.json"),
};

function isLanguage(value: string | null): value is Language {
  return SUPPORTED_LANGUAGES.includes(value as Language);
}

function readSavedLanguage(): Language {
  try {
    const saved = localStorage.getItem("language");
    return isLanguage(saved) ? saved : "fa";
  } catch {
    return "fa";
  }
}

export async function loadLanguage(lang: string): Promise<Language> {
  const target: Language = isLanguage(lang) ? lang : "fa";
  if (!i18n.hasResourceBundle(target, "translation")) {
    const { default: strings } = await loaders[target]();
    i18n.addResourceBundle(target, "translation", strings, true, true);
  }
  return target;
}

const savedLanguage = readSavedLanguage();

i18n.use(initReactI18next).init({
  resources: {},
  lng: savedLanguage,
  fallbackLng: "fa",
  ns: ["translation"],
  defaultNS: "translation",
  interpolation: { escapeValue: false },
  react: {
    useSuspense: false,
  },
});

export const i18nReady: Promise<void> = loadLanguage(savedLanguage).then(
  () => undefined,
  (err: unknown) => {
    console.error("Failed to load locale", err);
  },
);

export default i18n;
