export interface AvatarProps {
  src?: string | null;
  name?: string | null;
  size?: number;
  className?: string;
}

export function Avatar({ src, name, size = 48, className = "" }: AvatarProps) {
  const initial = (name || "کاربر").trim().charAt(0).toUpperCase();
  if (src) {
    return (
      <img
        src={src}
        alt={name || "کاربر"}
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
