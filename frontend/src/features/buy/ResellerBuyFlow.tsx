import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Server, Shuffle, Wallet, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import { PageHeader } from "../../components/layout/PageHeader";
import {
  Button,
  Card,
  CopyField,
  EmptyState,
  Input,
  StepProgress,
  StickyActionBar,
} from "../../components/ui";
import {
  ResellerModeBadge,
  ResellerPlanFeatureList,
  ResellerPlanGuide,
  resellerPlanPrice,
  resellerPlanSpecs,
} from "../../components/ResellerPlanGuide";
import { resellerApi } from "../../api/webapp";
import { useTelegram } from "../../hooks/useTelegram";
import { formatBytes, formatNumber, formatToman } from "../../lib/format";
import { resellerModeLabel } from "../../lib/resellerLabels";
import { useResellerBuyOptions, useResellerMutation } from "../../queries/useReseller";
import type {
  ResellerPanelItem,
  ResellerPlanItem,
  WebAppResellerBuyConfirmResponse,
  WebAppResellerBuyPreviewResponse,
} from "../../types/webapp";
import { Banner, ChoiceCard, InfoRow, STEP_MOTION, SelectionChip } from "./BuyChoices";

type Step = "panel" | "plan" | "confirm" | "success";
const STEPS: Step[] = ["panel", "plan", "confirm"];
const USERNAME_RE = /^[A-Za-z0-9][A-Za-z0-9_]{1,30}[A-Za-z0-9]$/;
/** Wait this long after the last keystroke before asking the server about the username. */
const PREVIEW_DEBOUNCE_MS = 450;

// Kept for older imports; the helper now lives with the shared plan guide.
export { resellerPlanPrice };

const PREPAID_MODES = ["fixed", "unlimited"];

function planTitle(t: TFunction, plan: ResellerPlanItem): string {
  return plan.name || resellerModeLabel(t, plan.pricing_mode);
}

interface PlanCardProps {
  plan: ResellerPlanItem;
  selected: boolean;
  onSelect: () => void;
}

/** A selectable plan: type, price, what it includes and what it allows. The full guide is on the confirm step. */
function ResellerPlanCard({ plan, selected, onSelect }: PlanCardProps) {
  const { t } = useTranslation();
  const prepaid = PREPAID_MODES.includes(plan.pricing_mode);
  return (
    // A div, not a button: the card holds a list, which a button may not contain.
    <div
      role="radio"
      tabIndex={0}
      aria-checked={selected}
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect();
        }
      }}
      className={`flex w-full cursor-pointer flex-col gap-3 rounded-lg border-[1.5px] p-3.5 text-start outline-none transition-colors focus-visible:ring-2 focus-visible:ring-primary/40 ${
        selected ? "border-primary bg-primary/6" : "border-border bg-surface hover:border-primary/40"
      }`}
    >
      <div className="flex w-full items-start gap-3">
        <span
          className={`mt-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 ${
            selected ? "border-primary" : "border-muted/40"
          }`}
        >
          {selected && <span className="h-2.5 w-2.5 rounded-full bg-primary" />}
        </span>
        <div className="min-w-0 flex-1 space-y-1.5">
          <p className="text-base font-extrabold text-text">{planTitle(t, plan)}</p>
          <ResellerModeBadge mode={plan.pricing_mode} />
        </div>
        <div className="shrink-0 text-end">
          <p className="text-sm font-extrabold text-text">{resellerPlanPrice(t, plan)}</p>
          {prepaid && <p className="mt-0.5 text-[10.5px] text-muted">{t("reseller.plan.oneTime")}</p>}
        </div>
      </div>
      <p className="w-full rounded-md bg-surface-2/70 px-3 py-2 text-xs font-medium text-text">
        {resellerPlanSpecs(t, plan)}
      </p>
      {/* The wallet rule is shown under the list once a usage/hourly plan is picked, and again on confirm. */}
      <ResellerPlanFeatureList plan={plan} showMinWallet={false} />
    </div>
  );
}

/** The amount paid up front; live-billed plans only charge their setup price here. */
function upfrontPrice(plan: ResellerPlanItem, volume: number): number {
  if (plan.pricing_mode === "per_gb" || plan.pricing_mode === "per_tb") return Math.round(plan.unit_price * volume);
  return plan.price;
}

export default function ResellerBuyFlow({ onExit }: { onExit: () => void }) {
  const { t } = useTranslation();
  const { haptic } = useTelegram();
  const options = useResellerBuyOptions();
  const minWallet = options.data?.min_wallet_balance ?? 0;

  const [step, setStep] = useState<Step>("panel");
  const [panel, setPanel] = useState<ResellerPanelItem | null>(null);
  const [plan, setPlan] = useState<ResellerPlanItem | null>(null);
  const [volume, setVolume] = useState("");
  const [username, setUsername] = useState("");
  const [discount, setDiscount] = useState("");
  const [discountDraft, setDiscountDraft] = useState("");
  const [discountError, setDiscountError] = useState("");
  const [preview, setPreview] = useState<WebAppResellerBuyPreviewResponse | null>(null);
  const [previewError, setPreviewError] = useState("");
  const confirmPlan = preview?.plan ?? null;
  const payAsYouGo = confirmPlan?.pricing_mode === "usage" || confirmPlan?.pricing_mode === "hourly";
  const [result, setResult] = useState<WebAppResellerBuyConfirmResponse | null>(null);
  const [error, setError] = useState("");
  // Key ("username|discount") of the request behind `preview`, and a counter so only the latest answer lands.
  const previewKey = useRef("");
  const previewSeq = useRef(0);

  const suggest = useResellerMutation(resellerApi.suggestUsername, { refresh: false });
  const previewCall = useResellerMutation(resellerApi.previewBuy, { refresh: false });
  const confirmCall = useResellerMutation(resellerApi.confirmBuy);

  const panels = options.data?.panels ?? [];

  // A single panel needs no choosing.
  useEffect(() => {
    if (step === "panel" && !panel && panels.length === 1) choosePanel(panels[0]!);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [panels.length]);

  const suggestUsername = (panelCode: number) =>
    suggest.mutate({ panel_code: panelCode }, { onSuccess: (res) => res.username && setUsername(res.username) });

  const choosePanel = (next: ResellerPanelItem) => {
    haptic.select();
    setPanel(next);
    setPlan(next.plans.length === 1 ? next.plans[0]! : null);
    setVolume("");
    setPreview(null);
    setError("");
    setStep("plan");
    if (!username) suggestUsername(next.code);
  };

  const volumeNumber = Number(volume.replace(/,/g, "")) || 0;
  const trimmedUsername = username.trim();
  const usernameValid = USERNAME_RE.test(trimmedUsername);
  const volumeOutOfRange =
    !!plan?.needs_volume &&
    volumeNumber > 0 &&
    (volumeNumber < (plan.min_volume || 0) || (plan.max_volume > 0 && volumeNumber > plan.max_volume));
  const volumeValid = !plan?.needs_volume || (volumeNumber > 0 && !volumeOutOfRange);

  const requestPreview = (code: string) => {
    if (!panel || !plan) return Promise.reject(new Error("No plan selected"));
    return previewCall.mutateAsync({
      panel_code: panel.code,
      plan_id: plan.id,
      username: trimmedUsername,
      volume: plan.needs_volume ? volumeNumber : null,
      discount_code: code || null,
    });
  };

  // The preview validates the username and checks it is free on the panel: re-run it (debounced) on every change.
  useEffect(() => {
    if (step !== "confirm" || !panel || !plan) return;
    if (!usernameValid) {
      setPreviewError("");
      return;
    }
    const key = `${trimmedUsername}|${discount}`;
    if (key === previewKey.current) return;
    const seq = ++previewSeq.current;
    const timer = window.setTimeout(() => {
      requestPreview(discount)
        .then((res) => {
          if (seq !== previewSeq.current) return;
          previewKey.current = key;
          setPreview(res);
          setPreviewError("");
        })
        .catch((err: Error) => {
          if (seq !== previewSeq.current) return;
          previewKey.current = "";
          setPreviewError(err.message);
        });
    }, preview || previewError ? PREVIEW_DEBOUNCE_MS : 0); // the first quote on this step needs no waiting
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, panel, plan, trimmedUsername, usernameValid, discount]);

  const previewFresh =
    !!preview && previewKey.current === `${trimmedUsername}|${discount}` && !previewError && usernameValid;
  const previewLoading = usernameValid && !previewFresh && !previewError;

  const goToConfirm = () => {
    haptic.impact("light");
    setError("");
    setPreview(null);
    setPreviewError("");
    previewKey.current = "";
    setStep("confirm");
  };

  const applyDiscount = async () => {
    const code = discountDraft.trim();
    if (!code) return;
    setDiscountError("");
    const seq = ++previewSeq.current;
    try {
      const res = await requestPreview(code);
      if (seq !== previewSeq.current) return;
      previewKey.current = `${trimmedUsername}|${code}`;
      setDiscount(code);
      setPreview(res);
      setPreviewError("");
    } catch (err) {
      setDiscountError((err as Error).message);
    }
  };

  const removeDiscount = () => {
    setDiscount("");
    setDiscountDraft("");
    setDiscountError("");
  };

  const confirm = async () => {
    if (!panel || !plan || !previewFresh) return;
    haptic.impact("medium");
    setError("");
    try {
      const res = await confirmCall.mutateAsync({
        panel_code: panel.code,
        plan_id: plan.id,
        username: trimmedUsername,
        volume: plan.needs_volume ? volumeNumber : null,
        discount_code: discount || null,
      });
      haptic.notify("success");
      setResult(res);
      setStep("success");
    } catch (err) {
      haptic.notify("error");
      setError((err as Error).message);
    }
  };

  const goBack = () => {
    setError("");
    if (step === "confirm") setStep("plan");
    else if (step === "plan" && panels.length > 1) setStep("panel");
    else onExit();
  };

  const titles: Record<Step, string> = {
    panel: t("reseller.buy.title"),
    plan: t("reseller.buy.choosePlan"),
    confirm: t("reseller.buy.confirmTitle"),
    success: t("reseller.buy.title"),
  };
  const stepLabels = [t("reseller.buy.stepPanel"), t("reseller.buy.stepPlan"), t("reseller.buy.stepConfirm")];
  const stepIndex = STEPS.indexOf(step);
  const usernameMessage = !username
    ? null
    : !usernameValid
      ? t("reseller.buy.usernameHint")
      : previewError || null;

  if (options.isLoading) {
    return (
      <div>
        <PageHeader title={titles.panel} back={onExit} />
        <Card className="h-24 animate-pulse bg-surface-2" />
      </div>
    );
  }

  if (options.error || !options.data?.enabled) {
    return (
      <div>
        <PageHeader title={titles.panel} back={onExit} />
        <EmptyState title={options.error ? (options.error as Error).message : t("reseller.buy.unavailable")} />
      </div>
    );
  }

  return (
    <div>
      {step !== "success" && <PageHeader title={titles[step]} back={goBack} />}

      <div className="space-y-4">
        {step !== "success" && <StepProgress current={stepIndex} total={STEPS.length} label={stepLabels[stepIndex]} />}
        {error && <Banner tone="danger">{error}</Banner>}

        <AnimatePresence mode="wait">
          {step === "panel" && (
            <motion.section key="panel" {...STEP_MOTION} className="grid gap-3 md:grid-cols-2">
              {panels.map((item) => (
                <ChoiceCard
                  key={item.code}
                  icon={Server}
                  tone="primary"
                  title={item.name}
                  description={t("reseller.buy.plansCount", { count: formatNumber(item.plans.length) })}
                  onSelect={() => choosePanel(item)}
                />
              ))}
            </motion.section>
          )}

          {step === "plan" && panel && (
            <motion.section key="plan" {...STEP_MOTION} className="space-y-4">
              {panels.length > 1 && (
                <div className="flex flex-wrap gap-2">
                  <SelectionChip label={panel.name} onChange={() => setStep("panel")} />
                </div>
              )}

              <div role="radiogroup" className="grid items-start gap-2.5 md:grid-cols-2">
                {panel.plans.map((item) => (
                  <ResellerPlanCard
                    key={item.id}
                    plan={item}
                    selected={plan?.id === item.id}
                    onSelect={() => {
                      haptic.select();
                      setPlan(item);
                      setVolume("");
                    }}
                  />
                ))}
              </div>

              {plan?.needs_wallet && (
                <p className="flex items-start gap-2 rounded-md bg-surface-2 px-3.5 py-3 text-xs leading-6 text-muted">
                  <Wallet size={14} className="mt-1 shrink-0 text-primary" />
                  {t(plan.pricing_mode === "hourly" ? "reseller.buy.hourlyNote" : "reseller.buy.usageNote", {
                    amount: formatToman(options.data.min_wallet_balance),
                  })}
                </p>
              )}

              {plan?.needs_volume && (
                <Input
                  label={t("reseller.buy.volume", {
                    unit: plan.pricing_mode === "per_tb" ? t("reseller.tb") : t("reseller.gb"),
                  })}
                  inputMode="decimal"
                  value={volume}
                  onChange={(event) => setVolume(event.target.value)}
                  placeholder={
                    plan.max_volume
                      ? t("reseller.buy.volumeRange", {
                          min: formatNumber(plan.min_volume),
                          max: formatNumber(plan.max_volume),
                        })
                      : undefined
                  }
                  error={
                    volumeOutOfRange
                      ? t("reseller.buy.volumeRange", {
                          min: formatNumber(plan.min_volume),
                          max: formatNumber(plan.max_volume),
                        })
                      : null
                  }
                  ltr
                />
              )}

              {plan && (
                <StickyActionBar
                  caption={planTitle(t, plan)}
                  amount={
                    plan.needs_volume && !volumeNumber
                      ? resellerPlanPrice(t, plan)
                      : formatToman(upfrontPrice(plan, volumeNumber))
                  }
                >
                  <Button type="button" size="lg" disabled={!volumeValid} onClick={goToConfirm}>
                    {t("reseller.buy.continue")}
                  </Button>
                </StickyActionBar>
              )}
            </motion.section>
          )}

          {step === "confirm" && panel && plan && (
            <motion.section key="confirm" {...STEP_MOTION} className="space-y-4">
              <div className="flex flex-wrap gap-2">
                {panels.length > 1 && <SelectionChip label={panel.name} onChange={() => setStep("panel")} />}
                <SelectionChip label={planTitle(t, plan)} onChange={() => setStep("plan")} />
              </div>

              <div className="space-y-1.5">
                <div className="flex items-end gap-2">
                  <Input
                    label={t("reseller.buy.username")}
                    value={username}
                    onChange={(event) => setUsername(event.target.value)}
                    placeholder="shop_ali"
                    autoComplete="off"
                    spellCheck={false}
                    aria-invalid={!!username && (!usernameValid || !!previewError)}
                    ltr
                  />
                  <Button
                    type="button"
                    variant="secondary"
                    className="h-10 shrink-0"
                    loading={suggest.isPending}
                    aria-label={t("reseller.buy.randomName")}
                    onClick={() => suggestUsername(panel.code)}
                  >
                    <Shuffle size={15} />
                  </Button>
                </div>
                <p
                  className={`px-1 text-xs leading-5 ${
                    username && (!usernameValid || previewError) ? "text-danger" : "text-muted"
                  }`}
                >
                  {usernameMessage ?? t("reseller.buy.usernameHint")}
                </p>
              </div>

              <Card className="space-y-2.5 p-4">
                <InfoRow label={t("reseller.plan.type")} value={resellerModeLabel(t, plan.pricing_mode)} />
                <InfoRow label={t("reseller.buy.pricing")} value={resellerPlanPrice(t, plan)} />
                {plan.needs_volume && volumeNumber > 0 ? (
                  <InfoRow
                    label={t("reseller.buy.volumeShort")}
                    value={`${formatNumber(preview?.volume ?? volumeNumber)} ${plan.pricing_mode === "per_tb" ? t("reseller.tb") : t("reseller.gb")}`}
                  />
                ) : null}
                {!plan.needs_volume && (
                  <InfoRow
                    label={t("reseller.buy.traffic")}
                    value={
                      plan.data_limit_bytes > 0
                        ? formatBytes(plan.data_limit_bytes)
                        : plan.pricing_mode === "usage" || plan.pricing_mode === "hourly"
                          ? t("reseller.plan.noVolumeCap")
                          : t("reseller.plan.unlimitedVolume")
                    }
                  />
                )}
                <InfoRow
                  label={t("reseller.buy.duration")}
                  value={
                    plan.duration_days > 0
                      ? t("renewFlow.days", { count: formatNumber(plan.duration_days) })
                      : t("reseller.noExpiry")
                  }
                />
                <InfoRow
                  label={t("reseller.buy.users")}
                  value={plan.max_users ? formatNumber(plan.max_users) : t("reseller.unlimitedUsers")}
                />
              </Card>

              <ResellerPlanGuide
                plan={preview?.plan ?? plan}
                graceDays={options.data.grace_days ?? 0}
                minWallet={options.data.min_wallet_balance}
              />

              {PREPAID_MODES.includes(plan.pricing_mode) &&
                (discount ? (
                  <div className="flex items-center justify-between gap-3 rounded-md border border-success/30 bg-success/5 px-3.5 py-2.5">
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-success">
                        {t("reseller.buy.discountApplied", { percent: formatNumber(preview?.discount_percent ?? 0) })}
                      </p>
                      <p className="truncate font-mono text-[13px] text-text" dir="ltr" style={{ textAlign: "start" }}>
                        {discount}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={removeDiscount}
                      aria-label={t("reseller.buy.removeDiscount")}
                      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-sm bg-surface-2 text-muted hover:text-text"
                    >
                      <X size={15} />
                    </button>
                  </div>
                ) : (
                  <div className="flex items-start gap-2">
                    <Input
                      value={discountDraft}
                      onChange={(event) => setDiscountDraft(event.target.value)}
                      placeholder={t("buy.discountCodePlaceholder")}
                      error={discountError || null}
                      ltr
                    />
                    <Button
                      type="button"
                      variant="secondary"
                      className="h-10 shrink-0"
                      loading={previewCall.isPending && !!discountDraft.trim()}
                      disabled={!discountDraft.trim() || !usernameValid}
                      onClick={() => void applyDiscount()}
                    >
                      {t("reseller.buy.apply")}
                    </Button>
                  </div>
                ))}

              {preview ? (
                <Card className={`space-y-2.5 p-4 transition-opacity ${previewFresh ? "" : "opacity-60"}`}>
                  <InfoRow label={t("buy.currentBalance")} value={formatToman(preview.balance)} />
                  {payAsYouGo ? (
                    <>
                      {/* Usage/hourly plans charge from the wallet over time; what matters at purchase is the minimum balance. */}
                      <InfoRow
                        label={t("reseller.buy.ratePrice")}
                        value={confirmPlan ? resellerPlanPrice(t, confirmPlan) : "—"}
                      />
                      {minWallet > 0 && (
                        <InfoRow label={t("reseller.buy.minWalletRequired")} value={formatToman(minWallet)} strong />
                      )}
                      <InfoRow
                        label={t("reseller.buy.upfront")}
                        value={preview.final_price > 0 ? formatToman(preview.final_price) : t("reseller.buy.noUpfront")}
                      />
                    </>
                  ) : (
                    <>
                      {preview.discount_percent > 0 && (
                        <InfoRow label={t("buy.basePrice")} value={formatToman(preview.base_price)} />
                      )}
                      <InfoRow label={t("buy.finalPrice")} value={formatToman(preview.final_price)} strong />
                    </>
                  )}
                  <div
                    className={`flex items-center justify-between gap-3 rounded-md border px-3.5 py-3 text-[13px] ${
                      preview.balance_after >= 0 ? "border-success/30 bg-success/5" : "border-danger/30 bg-danger/5"
                    }`}
                  >
                    <span className="text-muted">{t("buy.balanceAfter")}</span>
                    <span className={`font-extrabold ${preview.balance_after >= 0 ? "text-success" : "text-danger"}`}>
                      {formatToman(preview.balance_after)}
                    </span>
                  </div>
                </Card>
              ) : (
                previewLoading && <Card className="h-32 animate-pulse bg-surface-2" />
              )}

              {previewFresh && preview?.wallet_error && <Banner tone="warning">{preview.wallet_error}</Banner>}
              {previewFresh && preview && !preview.can_pay && (
                <Link
                  to="/balance"
                  className="flex h-11 items-center justify-center rounded-md border border-primary/30 bg-primary/5 text-sm font-semibold text-primary"
                >
                  {t("reseller.buy.topUp")}
                </Link>
              )}

              <StickyActionBar
                caption={
                  !preview
                    ? planTitle(t, plan)
                    : payAsYouGo && preview.final_price <= 0
                      ? t("reseller.buy.minWalletRequired")
                      : t("buy.finalPrice")
                }
                amount={
                  !preview
                    ? plan.needs_volume && !volumeNumber
                      ? resellerPlanPrice(t, plan)
                      : formatToman(upfrontPrice(plan, volumeNumber))
                    : formatToman(payAsYouGo && preview.final_price <= 0 ? minWallet : preview.final_price)
                }
              >
                <Button
                  type="button"
                  size="lg"
                  loading={confirmCall.isPending}
                  disabled={!previewFresh || !preview?.can_pay}
                  onClick={() => void confirm()}
                >
                  {t("reseller.buy.confirm")}
                </Button>
              </StickyActionBar>
            </motion.section>
          )}

          {step === "success" && result && (
            <motion.section
              key="success"
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              className="space-y-4"
            >
              <div className="flex flex-col items-center gap-2 py-4 text-center">
                <span className="flex h-16 w-16 items-center justify-center rounded-full bg-success/12 text-success">
                  <CheckCircle2 size={34} />
                </span>
                <h2 className="text-xl font-extrabold text-text">{t("reseller.buy.successTitle")}</h2>
                <p className="text-sm text-muted">
                  {t("reseller.buy.successPaid", { amount: formatToman(result.amount_paid) })}
                </p>
              </div>
              <Card className="space-y-2 p-4">
                {result.panel_url && <CopyField label={t("reseller.panelUrl")} value={result.panel_url} />}
                {result.username && <CopyField label={t("reseller.buy.username")} value={result.username} />}
                {result.password && <CopyField label={t("reseller.password")} value={result.password} />}
              </Card>
              <Banner tone="warning">{t("reseller.buy.savePassword")}</Banner>
              <div className="grid gap-2 sm:grid-cols-2">
                {result.account_code != null && (
                  <Link
                    to={`/services/reseller/${result.account_code}`}
                    className="flex h-11 items-center justify-center rounded-md bg-primary text-sm font-semibold text-primary-text"
                  >
                    {t("reseller.buy.manage")}
                  </Link>
                )}
                <Button type="button" variant="secondary" onClick={onExit}>
                  {t("reseller.buy.done")}
                </Button>
              </div>
            </motion.section>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
