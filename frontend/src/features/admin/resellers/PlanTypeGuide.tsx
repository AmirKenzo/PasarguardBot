import { Clock, Gauge, Infinity as InfinityIcon, Package } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { panelResellersApi } from "../../../api/panel";
import { formatNumber, formatToman } from "../../../lib/format";
import { usePanelQuery } from "../../../queries/usePanelApi";
import { CREATABLE_MODES, FIXED, HOURLY, UNLIMITED, USAGE, ruleFor } from "./planRules";
import { pricingLabels, pricingShortLabels } from "./labels";

const TYPE_ICONS: Record<string, LucideIcon> = {
  [FIXED]: Package,
  [UNLIMITED]: InfinityIcon,
  [USAGE]: Gauge,
  [HOURLY]: Clock,
};

/** The four plan types as tiles; `disabled` keeps the current type (a plan with linked accounts). */
export function PlanTypeTiles({
  value,
  onChange,
  disabled = false,
}: {
  value: string;
  onChange: (mode: string) => void;
  disabled?: boolean;
}) {
  const { t } = useTranslation();
  const short = pricingShortLabels(t);
  return (
    <div role="radiogroup" aria-label={t("panel.resellerHub.planType")} className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {CREATABLE_MODES.map((mode) => {
        const Icon = TYPE_ICONS[mode] ?? Package;
        const active = mode === value;
        return (
          <button
            key={mode}
            type="button"
            role="radio"
            aria-checked={active}
            disabled={disabled && !active}
            onClick={() => onChange(mode)}
            className={`flex flex-col items-start gap-1 rounded-xl border p-3 text-start transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
              active ? "border-primary bg-primary/10 text-primary" : "border-border text-text hover:border-primary/40"
            }`}
          >
            <Icon size={18} />
            <span className="text-sm font-semibold">{short[mode]}</span>
            <span className={`text-[11px] leading-5 ${active ? "text-primary/80" : "text-muted"}`}>
              {t(`panel.resellerHub.planForm.tile.${mode}`)}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function lines(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function GuideSection({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div>
      <p className="mb-1 text-xs font-semibold text-text">{title}</p>
      <ul className="list-disc space-y-1 ps-5 text-xs leading-6 text-muted marker:text-primary/60">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Full admin guide for one plan type: what it is, required fields, what the buyer can do, what the
 * bot does on its own, and notes. The bot's numbers (grace days, minimum wallet) come from the
 * reseller settings so the guide matches what will actually happen.
 */
export function PlanTypeGuide({ mode }: { mode: string }) {
  const { t } = useTranslation();
  const settings = usePanelQuery(["reseller-settings"], (auth) => panelResellersApi.getSettings(auth), {
    staleTime: 60_000,
  });
  const rule = ruleFor(mode);
  const values = settings.data?.settings;
  const grace = values?.grace_days ?? 7;
  const lowHours = values?.low_balance_hours ?? 6;
  const minWallet = values?.min_wallet_balance ?? 0;
  const base = `panel.resellerHub.guide.${mode}`;
  const vars = { grace: formatNumber(grace), lowHours: formatNumber(lowHours), returnObjects: true as const };

  const auto = lines(t(`${base}.auto`, vars));
  if (rule.needsWallet) {
    auto.push(
      minWallet > 0
        ? t("panel.resellerHub.guide.minWallet", { amount: formatToman(minWallet) })
        : t("panel.resellerHub.guide.noMinWallet")
    );
  }

  return (
    <div className="space-y-3 rounded-xl border border-primary/20 bg-primary/5 p-3.5">
      <div>
        <p className="text-sm font-semibold text-primary">
          {t("panel.resellerHub.guide.heading", { type: pricingLabels(t)[mode] || mode })}
        </p>
        <p className="mt-1 text-xs leading-6 text-text">{t(`${base}.what`)}</p>
      </div>
      <GuideSection title={t("panel.resellerHub.guide.sections.fields")} items={lines(t(`${base}.fields`, vars))} />
      <GuideSection title={t("panel.resellerHub.guide.sections.buyer")} items={lines(t(`${base}.buyer`, vars))} />
      <GuideSection title={t("panel.resellerHub.guide.sections.auto")} items={auto} />
      <GuideSection title={t("panel.resellerHub.guide.sections.notes")} items={lines(t(`${base}.notes`, vars))} />
    </div>
  );
}
