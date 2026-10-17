import { Home, Layers, ShoppingCart, User } from "lucide-react";
import { useTranslation } from "react-i18next";
import { themeStyle } from "../../../../design/webappThemes";
import type { Scheme, WebappTheme } from "../../../../design/webappThemes";

function UsageRing({ percent }: { percent: number }) {
  const r = 26;
  const c = 2 * Math.PI * r;
  return (
    <svg viewBox="0 0 64 64" className="h-16 w-16 shrink-0" aria-hidden>
      <circle cx="32" cy="32" r={r} fill="none" stroke="rgb(var(--c-surface-2-rgb))" strokeWidth="7" />
      <circle
        cx="32"
        cy="32"
        r={r}
        fill="none"
        stroke="rgb(var(--c-primary-rgb))"
        strokeWidth="7"
        strokeLinecap="round"
        strokeDasharray={`${c * percent} ${c}`}
        transform="rotate(-90 32 32)"
      />
      <text x="32" y="37" textAnchor="middle" fontSize="14" fontWeight="800" fill="rgb(var(--c-text-rgb))">
        {Math.round(percent * 100)}%
      </text>
    </svg>
  );
}

/**
 * A phone-sized mock of the user dashboard drawn with the real design tokens,
 * scoped to this element, so it shows exactly what a theme does to the app.
 */
export function ThemePreviewPhone({ theme, scheme }: { theme: WebappTheme; scheme: Scheme }) {
  const { t } = useTranslation();
  const p = (key: string) => t(`panel.webappThemes.preview.${key}`);
  const nav = [
    { icon: Home, label: p("navHome"), active: true },
    { icon: ShoppingCart, label: p("navBuy") },
    { icon: Layers, label: p("navServices") },
    { icon: User, label: p("navProfile") },
  ];

  return (
    <div className="w-full max-w-[340px] rounded-[44px] bg-[#0b0c10] p-2.5 shadow-lg ring-1 ring-white/10">
      <div
        style={themeStyle(theme, scheme)}
        className="relative flex aspect-[340/700] max-h-[700px] flex-col overflow-hidden rounded-[34px] bg-bg text-text transition-colors duration-300"
      >
        <div className="flex h-12 shrink-0 items-end justify-between border-b border-border bg-surface px-4 pb-2 text-xs font-semibold">
          <span className="text-accent">{p("close")}</span>
          <span>{p("botName")}</span>
          <span className="text-muted">⋯</span>
        </div>

        <div className="no-scrollbar flex flex-1 flex-col gap-3 overflow-y-auto p-3.5">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/15 text-sm font-bold text-primary">
              {p("avatar")}
            </span>
            <div className="min-w-0">
              <p className="text-sm font-bold">{p("hello")}</p>
              <p className="text-2xs text-muted">{p("lastSeen")}</p>
            </div>
          </div>

          <div className="flex items-center justify-between gap-2 rounded-lg bg-gradient-to-br from-primary to-primary-strong p-3.5 text-primary-text shadow-md">
            <div>
              <p className="text-2xs opacity-80">{p("balance")}</p>
              <p className="text-lg font-extrabold">{p("balanceValue")}</p>
            </div>
            <span className="rounded-md bg-primary-text/20 px-3 py-1.5 text-xs font-bold">{p("topUp")}</span>
          </div>

          <div className="rounded-lg border border-border bg-surface p-3.5 shadow-sm">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-bold">{p("service1")}</p>
              <span className="rounded-full bg-success/15 px-2 py-0.5 text-3xs font-bold text-success">
                {p("active")}
              </span>
            </div>
            <div className="my-2.5 flex items-center gap-3">
              <UsageRing percent={0.62} />
              <div className="flex flex-col gap-0.5 text-2xs text-muted">
                <span>{p("usage")}</span>
                <span className="text-xs-plus font-bold text-text">{p("usageValue")}</span>
                <span>{p("daysLeft")}</span>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <span className="flex h-9 items-center justify-center rounded-md bg-gradient-to-l from-primary to-primary-strong text-xs font-bold text-primary-text shadow-md shadow-primary/30">
                {p("renew")}
              </span>
              <span className="flex h-9 items-center justify-center rounded-md border border-border bg-surface-2 text-xs font-bold">
                {p("subLink")}
              </span>
            </div>
          </div>

          <div className="rounded-lg border border-border bg-surface p-3 shadow-sm">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs-plus font-bold">{p("service2")}</p>
              <span className="rounded-full bg-warning/15 px-2 py-0.5 text-3xs font-bold text-warning">
                {p("ending")}
              </span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-2">
              <div className="h-full w-[91%] rounded-full bg-warning" />
            </div>
            <p className="mt-1 text-2xs text-muted">{p("service2Detail")}</p>
          </div>

          <div className="flex items-center justify-between gap-2 rounded-lg border border-border bg-surface p-3 shadow-sm">
            <div>
              <p className="text-xs-plus font-bold">{p("service3")}</p>
              <p className="text-2xs text-muted">{p("service3Detail")}</p>
            </div>
            <span className="rounded-full bg-danger/15 px-2 py-0.5 text-3xs font-bold text-danger">{p("expired")}</span>
          </div>

          <div className="flex gap-1.5">
            <span className="flex h-9 flex-1 items-center rounded-md border border-border bg-surface-2 px-2.5 text-xs text-muted">
              {p("discount")}
            </span>
            <span className="flex h-9 items-center rounded-md border border-border bg-surface-2 px-3 text-xs font-bold">
              {p("apply")}
            </span>
          </div>
          <p className="text-center text-xs font-semibold text-accent">{p("plans")}</p>
          <div className="h-10 shrink-0" />
        </div>

        <div className="absolute inset-x-3.5 bottom-[70px] flex items-center gap-2 rounded-md border border-border bg-surface px-3 py-2 text-2xs shadow-md">
          <span className="h-2 w-2 shrink-0 rounded-full bg-success" />
          {p("toast")}
        </div>

        <div className="grid h-16 shrink-0 grid-cols-4 border-t border-border bg-surface pb-1.5">
          {nav.map((item) => (
            <div
              key={item.label}
              className={`flex flex-col items-center justify-center gap-0.5 text-3xs font-semibold ${
                item.active ? "text-primary" : "text-muted"
              }`}
            >
              <item.icon size={19} />
              {item.label}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
