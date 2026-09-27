import { Globe } from "lucide-react";
import { useLanguage } from "../../context/LanguageContext";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";

export function LanguageToggle() {
  const { language, setLanguage } = useLanguage();
  const { i18n } = useTranslation();

  const handleLanguageChange = () => {
    const newLang = language === "fa" ? "en" : "fa";
    setLanguage(newLang);
  };

  return (
    <div className="flex items-center gap-2">
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
