import { useTranslation } from "react-i18next";

export function AppVersion({ className = "" }: { className?: string }) {
  const { t } = useTranslation();
  return (
    <span className={`select-none text-[10px] tracking-wide text-muted/70 ${className}`}>
      {t("ui.version", { version: __APP_VERSION__ })}
    </span>
  );
}
