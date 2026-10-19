import type { Palette, WebappTheme } from "../../../../design/webappThemes";
import { hexToRgb } from "../../../../design/webappThemes";

function Half({ palette, radius }: { palette: Palette; radius: number }) {
  const border = `rgb(${hexToRgb(palette.text).join(" ")} / ${palette.border_alpha})`;
  return (
    <div className="flex min-w-0 flex-1 flex-col gap-1.5 p-2.5" style={{ background: palette.bg }}>
      <span className="h-1.5 w-3/5 rounded-full opacity-85" style={{ background: palette.text }} />
      <span className="h-1.5 w-2/5 rounded-full opacity-60" style={{ background: palette.text_muted }} />
      <div
        className="mt-auto flex flex-col gap-1 p-1.5"
        style={{ background: palette.surface, border: `1px solid ${border}`, borderRadius: Math.max(4, radius * 0.55) }}
      >
        <span className="h-1 w-1/3 rounded-full" style={{ background: palette.success }} />
        <span
          className="h-3"
          style={{
            background: `linear-gradient(to left, ${palette.primary}, ${palette.primary_strong})`,
            borderRadius: Math.max(3, radius * 0.35),
          }}
        />
      </div>
    </div>
  );
}

/** A light half and a dark half of the same theme, so both versions are judged at a glance. */
export function ThemeThumb({ theme, className = "" }: { theme: WebappTheme; className?: string }) {
  return (
    <div className={`flex h-24 overflow-hidden ${className}`} aria-hidden>
      <Half palette={theme.light} radius={theme.radius} />
      <Half palette={theme.dark} radius={theme.radius} />
    </div>
  );
}
