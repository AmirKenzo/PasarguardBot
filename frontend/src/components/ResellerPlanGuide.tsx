/**
 * Reseller plan explanations shared by the buy flow and the reseller account page:
 * the type badge, the price line, the "what this plan allows" checklist and the
 * "how does this plan work?" guide. Everything is generated from the plan's real
 * settings, so an add-on that is switched off is never promised.
 */
import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, ChevronDown, HelpCircle, Minus } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import { formatBytes, formatNumber, formatToman } from "../lib/format";
import { MODE_TONE, resellerModeLabel } from "../lib/resellerLabels";
import type { ResellerPlanFeatures, ResellerPlanItem } from "../types/webapp";
import { Badge } from "./ui";

const PAYG_MODES = ["usage", "hourly"];

/** The plan's features; older servers send none, so fall back to what the type implies (no add-ons). */
export function resolvePlanFeatures(plan: ResellerPlanItem): ResellerPlanFeatures {
  if (plan.features) return plan.features;
  const prepaid = plan.pricing_mode === "fixed" || plan.pricing_mode === "unlimited";
  return {
    renewable: prepaid,
    expires: prepaid || plan.duration_days > 0,
    unlimited_volume: plan.data_limit_bytes <= 0,
    usage_cap: plan.pricing_mode === "usage",
    needs_wallet: plan.needs_wallet,
    extra_day_price: 0,
    extra_gb_price: 0,
    extra_user_price: 0,
  };
}

/** What the plan costs, in its own unit (package price, per GB used, per active hour...). */
export function resellerPlanPrice(t: TFunction, plan: ResellerPlanItem): string {
  switch (plan.pricing_mode) {
    case "hourly":
      return t("reseller.perActiveHour", { amount: formatToman(plan.unit_price) });
    case "usage":
      return t("reseller.perGbUsed", { amount: formatToman(plan.unit_price) });
    case "per_gb":
      return t("reseller.perGb", { amount: formatToman(plan.unit_price) });
    case "per_tb":
      return t("reseller.perTb", { amount: formatToman(plan.unit_price) });
    default:
      return formatToman(plan.price);
  }
}

function usersText(t: TFunction, maxUsers: number): string {
  return maxUsers > 0 ? t("reseller.usersCount", { count: formatNumber(maxUsers) }) : t("reseller.unlimitedUsers");
}

/** One line of what the plan includes: volume · days · users, worded per type. */
export function resellerPlanSpecs(t: TFunction, plan: ResellerPlanItem): string {
  const features = resolvePlanFeatures(plan);
  const parts: string[] = [];
  if (PAYG_MODES.includes(plan.pricing_mode)) {
    parts.push(
      features.unlimited_volume
        ? t("reseller.plan.noVolumeCap")
        : t("reseller.plan.volumeCap", { volume: formatBytes(plan.data_limit_bytes) })
    );
    if (!features.expires) parts.push(t("reseller.noExpiry"));
  } else if (!plan.needs_volume) {
    parts.push(features.unlimited_volume ? t("reseller.plan.unlimitedVolume") : formatBytes(plan.data_limit_bytes));
  }
  if (plan.duration_days > 0) parts.push(t("renewFlow.days", { count: formatNumber(plan.duration_days) }));
  parts.push(usersText(t, plan.max_users));
  return parts.join(" · ");
}

export function ResellerModeBadge({ mode }: { mode: string }) {
  const { t } = useTranslation();
  return <Badge tone={MODE_TONE[mode] || "muted"}>{resellerModeLabel(t, mode)}</Badge>;
}

// --------------------------------------------------------------------------- //
//  "What this plan allows" checklist                                            //
// --------------------------------------------------------------------------- //

interface FeatureRow {
  key: string;
  on: boolean;
  label: string;
  detail: string;
}

function featureRows(
  t: TFunction,
  plan: ResellerPlanItem,
  { minWallet, showMinWallet }: { minWallet: number; showMinWallet: boolean }
): FeatureRow[] {
  const f = resolvePlanFeatures(plan);
  const payg = PAYG_MODES.includes(plan.pricing_mode);
  const off = t("reseller.plan.off");
  const noExpiry = t("reseller.plan.notNeededNoExpiry");
  const rows: FeatureRow[] = [
    {
      key: "renew",
      on: f.renewable,
      label: t("reseller.plan.renewal"),
      detail: f.renewable ? t("reseller.plan.renewalOn", { price: formatToman(plan.price) }) : f.expires ? off : noExpiry,
    },
    {
      key: "days",
      on: f.extra_day_price > 0,
      label: t("reseller.plan.extraDays"),
      detail:
        f.extra_day_price > 0
          ? t("reseller.plan.perDay", { price: formatToman(f.extra_day_price) })
          : f.expires
            ? off
            : noExpiry,
    },
    {
      key: "volume",
      on: f.extra_gb_price > 0,
      label: t("reseller.plan.extraVolume"),
      detail:
        f.extra_gb_price > 0
          ? t("reseller.plan.perGb", { price: formatToman(f.extra_gb_price) })
          : f.unlimited_volume && !plan.needs_volume
            ? t(payg ? "reseller.plan.notNeededNoCap" : "reseller.plan.notNeededUnlimited")
            : off,
    },
    {
      key: "users",
      on: f.extra_user_price > 0 && plan.max_users > 0,
      label: t("reseller.plan.extraUsers"),
      detail:
        plan.max_users <= 0
          ? t("reseller.plan.notNeededUnlimitedUsers")
          : f.extra_user_price > 0
            ? t("reseller.plan.perUser", { price: formatToman(f.extra_user_price) })
            : off,
    },
    {
      key: "cap",
      on: f.usage_cap,
      label: t("reseller.plan.usageCap"),
      detail: f.usage_cap ? t("reseller.plan.usageCapOn") : off,
    },
  ];
  if (showMinWallet) {
    const needed = f.needs_wallet && minWallet > 0;
    rows.push({
      key: "wallet",
      on: needed,
      label: t("reseller.plan.minWallet"),
      detail: needed ? formatToman(minWallet) : t("reseller.plan.notRequired"),
    });
  }
  return rows;
}

export interface ResellerPlanFeatureListProps {
  plan: ResellerPlanItem;
  /** Minimum wallet balance to buy usage/hourly plans (buy options). */
  minWallet?: number;
  /** Hide the purchase-only wallet row (e.g. on an account that is already bought). */
  showMinWallet?: boolean;
}

/** ✓ / – list of renewal, add-ons with their prices, usage cap and the wallet rule. */
export function ResellerPlanFeatureList({ plan, minWallet = 0, showMinWallet = true }: ResellerPlanFeatureListProps) {
  const { t } = useTranslation();
  return (
    <ul className="space-y-1.5" aria-label={t("reseller.plan.allowsTitle")}>
      {featureRows(t, plan, { minWallet, showMinWallet }).map((row) => (
        <li key={row.key} className="flex items-start gap-2 text-xs leading-5">
          <span
            className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full ${
              row.on ? "bg-success/15 text-success" : "bg-surface-2 text-muted"
            }`}
            aria-hidden
          >
            {row.on ? <Check size={11} strokeWidth={3} /> : <Minus size={11} strokeWidth={3} />}
          </span>
          <span className={`shrink-0 font-semibold ${row.on ? "text-text" : "text-muted"}`}>{row.label}</span>
          <span className="min-w-0 flex-1 text-end text-muted">{row.detail}</span>
          <span className="sr-only">{row.on ? t("reseller.plan.srOn") : t("reseller.plan.srOff")}</span>
        </li>
      ))}
    </ul>
  );
}

// --------------------------------------------------------------------------- //
//  "How does this plan work?" guide                                             //
// --------------------------------------------------------------------------- //

export interface PlanGuideSection {
  key: string;
  title: string;
  lines: string[];
}

export interface PlanGuideOptions {
  /** Days an expired reseller is kept before it is purged. */
  graceDays: number;
  minWallet: number;
  showMinWallet?: boolean;
}

/** The plan explained in plain sentences, section by section, from its real settings. */
export function buildPlanGuide(t: TFunction, plan: ResellerPlanItem, options: PlanGuideOptions): PlanGuideSection[] {
  const f = resolvePlanFeatures(plan);
  const mode = plan.pricing_mode;
  const payg = PAYG_MODES.includes(mode);
  const prepaid = mode === "fixed" || mode === "unlimited";
  const hasVolume = !f.unlimited_volume && !plan.needs_volume;
  const price = formatToman(plan.price);
  const rate = formatToman(plan.unit_price);
  const volume = formatBytes(plan.data_limit_bytes);
  const days = formatNumber(plan.duration_days);
  const grace = formatNumber(Math.max(1, options.graceDays || 0));
  const sections: PlanGuideSection[] = [];

  // Payment
  const payment: string[] = [];
  if (prepaid && hasVolume) payment.push(t("reseller.guide.payFixed", { price, volume, days }));
  else if (prepaid) payment.push(t("reseller.guide.payUnlimited", { price, days }));
  else if (mode === "usage") payment.push(t("reseller.guide.payUsage", { rate }));
  else if (mode === "hourly") payment.push(t("reseller.guide.payHourly", { rate }));
  else payment.push(t("reseller.guide.payLegacy", { rate: resellerPlanPrice(t, plan) }));
  if (payg) payment.push(t("reseller.guide.liveRate"));
  else if (f.renewable) payment.push(t("reseller.guide.priceLocked"));
  if (f.needs_wallet && options.showMinWallet !== false && options.minWallet > 0) {
    payment.push(t("reseller.guide.minWallet", { amount: formatToman(options.minWallet) }));
  }
  sections.push({ key: "payment", title: t("reseller.guide.payment"), lines: payment });

  // Volume and users
  const limits: string[] = [];
  if (plan.needs_volume) limits.push(t("reseller.guide.volumeChosen"));
  else if (payg) {
    limits.push(
      f.unlimited_volume
        ? t(mode === "usage" ? "reseller.guide.volumeNoCapUsage" : "reseller.guide.volumeNoCap")
        : t("reseller.guide.volumeCap", { volume })
    );
  } else limits.push(hasVolume ? t("reseller.guide.volumeFixed", { volume }) : t("reseller.guide.volumeUnlimited"));
  if (f.usage_cap) limits.push(t("reseller.guide.usageCap"));
  limits.push(
    plan.max_users > 0
      ? t("reseller.guide.usersLimited", { count: formatNumber(plan.max_users) })
      : t("reseller.guide.usersUnlimited")
  );
  sections.push({ key: "limits", title: t("reseller.guide.limits"), lines: limits });

  // Expiry, or what happens when the wallet runs out
  const expiry: string[] = [];
  if (f.expires) {
    if (plan.duration_days > 0) expiry.push(t("reseller.guide.expires", { days }));
    const graceKey =
      f.extra_day_price > 0
        ? f.renewable
          ? "reseller.guide.graceRenewOrDays"
          : "reseller.guide.graceDaysOnly"
        : f.renewable
          ? "reseller.guide.graceRenew"
          : "reseller.guide.graceOnly";
    expiry.push(t(graceKey, { grace }));
  } else {
    expiry.push(t(f.needs_wallet ? "reseller.guide.noExpiryWallet" : "reseller.guide.noExpiry"));
  }
  if (f.needs_wallet) expiry.push(t("reseller.guide.walletEmpty"));
  sections.push({ key: "expiry", title: t("reseller.guide.expiry"), lines: expiry });

  // Renewal
  if (f.renewable) {
    const renewal = [t("reseller.guide.renewRule", { price, days })];
    if (hasVolume) renewal.push(t("reseller.guide.renewVolume", { volume }));
    renewal.push(t("reseller.guide.renewNoReset"));
    sections.push({ key: "renew", title: t("reseller.guide.renewal"), lines: renewal });
  } else if (!f.expires) {
    sections.push({ key: "renew", title: t("reseller.guide.renewal"), lines: [t("reseller.guide.noRenew")] });
  }

  // Add-ons: only the ones this plan really sells
  const addons: string[] = [];
  if (f.extra_day_price > 0) addons.push(t("reseller.guide.addonDays", { price: formatToman(f.extra_day_price) }));
  if (f.extra_gb_price > 0) addons.push(t("reseller.guide.addonVolume", { price: formatToman(f.extra_gb_price) }));
  if (f.extra_user_price > 0 && plan.max_users > 0) {
    addons.push(
      t(f.renewable ? "reseller.guide.addonUsersRenewable" : "reseller.guide.addonUsers", {
        price: formatToman(f.extra_user_price),
      })
    );
  }
  if (addons.length && f.renewable) addons.push(t("reseller.guide.addonsPermanent"));
  if (addons.length) sections.push({ key: "addons", title: t("reseller.guide.addons"), lines: addons });

  return sections;
}

export interface ResellerPlanGuideProps extends PlanGuideOptions {
  plan: ResellerPlanItem;
  defaultOpen?: boolean;
}

/** Expandable "How does this plan work?" explanation. */
export function ResellerPlanGuide({ plan, graceDays, minWallet, showMinWallet = true, defaultOpen = false }: ResellerPlanGuideProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(defaultOpen);
  const sections = buildPlanGuide(t, plan, { graceDays, minWallet, showMinWallet });

  return (
    <div className="rounded-md border border-border bg-surface-2/50">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center gap-2 px-3 py-2.5 text-start text-xs font-semibold text-primary"
      >
        <HelpCircle size={15} className="shrink-0" />
        <span className="flex-1">{t("reseller.guide.title")}</span>
        <motion.span animate={{ rotate: open ? 180 : 0 }} className="text-muted">
          <ChevronDown size={16} />
        </motion.span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="space-y-3 px-3 pb-3">
              {sections.map((section) => (
                <section key={section.key}>
                  <h4 className="mb-1 text-xs font-bold text-text">{section.title}</h4>
                  <ul className="list-disc space-y-1 ps-4 text-xs leading-6 text-muted marker:text-primary/60">
                    {section.lines.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                </section>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
