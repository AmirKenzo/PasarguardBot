import { Globe, Moon, Sun } from "lucide-react";
import { useTheme } from "../../design/ThemeProvider";
import { useLanguage } from "../../context/LanguageContext";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";

export function LanguageToggle() {
  const { scheme, mode, setMode } = useTheme();
  const { language, setLanguage } = useLanguage();
  const { i18n } = useTranslation();

  const toggleTheme = () => {
    if (mode === "auto") {
      setMode(scheme === "dark" ? "light" : "dark");
    } else {
      setMode(mode === "dark" ? "light" : "dark");
    }
  };

  const handleLanguageChange = () => {
    const newLang = language === "fa" ? "en" : "fa";
    setLanguage(newLang);
  };

  const isDark = mode === "dark" || (mode === "auto" && scheme === "dark");

  return (
    <div className="flex items-center gap-2">
      <motion.button
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={toggleTheme}
        className="flex items-center justify-center rounded-lg bg-primary/10 p-2.5 text-primary transition-colors hover:bg-primary/20"
        title={isDark ? "Light Mode" : "Dark Mode"}
      >
        {isDark ? <Sun size={18} /> : <Moon size={18} />}
      </motion.button>

      <motion.button
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={handleLanguageChange}
        className="flex items-center justify-center rounded-lg bg-primary/10 p-2.5 text-primary transition-colors hover:bg-primary/20"
        title={i18n.language === "fa" ? "English" : "فارسی"}
      >
        <Globe size={18} />
        <span className="ms-1.5 text-xs font-bold">{i18n.language === "fa" ? "EN" : "FA"}</span>
      </motion.button>
    </div>
  );
}
