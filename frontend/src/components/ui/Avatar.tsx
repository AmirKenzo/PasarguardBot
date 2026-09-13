import { useTranslation } from "react-i18next";

export interface AvatarProps {
  src?: string | null;
  name?: string | null;
  size?: number;
  className?: string;
}

export function Avatar({ src, name, size = 48, className = "" }: AvatarProps) {
  const { t } = useTranslation();
  const fallbackName = name || t("common.user");
  const initial = fallbackName.trim().charAt(0).toUpperCase();
  if (src) {
    return (
      <img
        src={src}
        alt={fallbackName}
        className={`rounded-full object-cover ${className}`}
        style={{ width: size, height: size }}
      />
    );
  }
  return (
    <div
      className={`flex items-center justify-center rounded-full bg-gradient-to-br from-primary to-accent font-semibold text-primary-text ${className}`}
      style={{ width: size, height: size, fontSize: size * 0.4 }}
    >
      {initial}
    </div>
  );
}
