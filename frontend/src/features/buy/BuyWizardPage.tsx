import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { EmojiIcon } from "../../components/EmojiIcon";
import { Button, Card, EmptyState, Input, Stepper } from "../../components/ui";
import { ErrorState } from "../../components/ui/EmptyState";
import { useTelegram } from "../../hooks/useTelegram";
import { copyToClipboard, formatNumber, formatToman } from "../../lib/format";
import {
  useBuyConfirmMutation,
  useBuyOptionsQuery,
  useBuyPlansQuery,
  useBuyPreviewMutation,
  useGenerateBuyUsernameMutation,
} from "../../queries/useBuyFlow";
import { buyApi } from "../../api/webapp";
import { useWebAppAuth } from "../../hooks/useWebAppAuth";
import type { WebAppBuyPanelItem, WebAppBuyPlanItem, WebAppBuyPreviewResponse } from "../../types/webapp";

type BuyStep = "panel" | "duration" | "plan" | "username" | "confirm" | "success";

const STEP_LABELS = ["پنل", "زمان", "پلن", "نام", "تأیید", "تحویل"];

function randomConfigName() {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  return Array.from({ length: 8 }, () => chars[Math.floor(Math.random() * chars.length)] ?? "X").join("");
}

function InfoRow({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex justify-between gap-3 text-sm">
      <span className="text-muted">{label}</span>
      <span className={strong ? "font-semibold text-primary" : "text-text"}>{value}</span>
    </div>
  );
}

function PanelSummary({ panel, duration }: { panel: WebAppBuyPanelItem | null; duration?: number | null }) {
  if (!panel) return null;
  return (
    <Card className="p-4">
      <p className="text-xs text-muted">پنل انتخابی</p>
      <p className="mt-1 text-lg font-black text-text">{panel.name}</p>
      {duration != null && <p className="mt-1 text-sm text-muted">{duration} روزه</p>}
    </Card>
  );
}

function PlanSummary({ plan }: { plan: WebAppBuyPlanItem }) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-lg font-black text-text">{plan.plan_name}</p>
          <p className="mt-1 text-sm text-muted">
            {plan.duration} روزه • {plan.ip_limit > 0 ? `${plan.ip_limit} کاربر` : "نامحدود کاربر"}
          </p>
        </div>
        <span className="rounded-md bg-primary/10 px-3 py-2 text-sm font-bold text-primary ring-1 ring-primary/20">
          {formatNumber(plan.price)}
        </span>
      </div>
    </Card>
  );
}

export default function BuyWizardPage() {
  const { haptic } = useTelegram();
  const { auth } = useWebAppAuth();
  const queryClient = useQueryClient();

  const [step, setStep] = useState<BuyStep>("panel");
  const [selectedPanel, setSelectedPanel] = useState<WebAppBuyPanelItem | null>(null);
  const [selectedDuration, setSelectedDuration] = useState<number | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<WebAppBuyPlanItem | null>(null);
  const [username, setUsername] = useState("");
  const [discountCode, setDiscountCode] = useState("");
  const [preview, setPreview] = useState<WebAppBuyPreviewResponse | null>(null);
  const [flowError, setFlowError] = useState("");

  const { data: options, isLoading: optionsLoading, error: optionsError } = useBuyOptionsQuery();
  const { data: plansResponse, isLoading: plansLoading } = useBuyPlansQuery(
    selectedPanel?.code ?? null,
    selectedDuration
  );
  const generateUsername = useGenerateBuyUsernameMutation();
  const previewBuy = useBuyPreviewMutation();
  const confirmBuy = useBuyConfirmMutation();

  const stepIndex = useMemo(() => {
    const order: BuyStep[] = ["panel", "duration", "plan", "username", "confirm", "success"];
    return order.indexOf(step);
  }, [step]);

  const plansForDuration = useMemo(() => {
    const plans = plansResponse?.plans ?? [];
    return selectedDuration == null ? plans : plans.filter((plan) => plan.duration === selectedDuration);
  }, [plansResponse?.plans, selectedDuration]);

  useEffect(() => {
    if (!options?.ok || !options.single_panel_buy_mode || !auth) return;
    const panels = options.panels ?? [];
    if (panels.length !== 1 || selectedPanel) return;
    void selectPanel(panels[0]!);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options?.ok, options?.single_panel_buy_mode, auth]);

  const selectPanel = async (panel: WebAppBuyPanelItem) => {
    if (!auth) return;
    haptic.select();
    setSelectedPanel(panel);
    setSelectedDuration(null);
    setSelectedPlan(null);
    setPreview(null);
    setFlowError("");
    const plansData = await queryClient.fetchQuery({
      queryKey: ["buy-plans", panel.code, null, auth.session_token, auth.init_data],
      queryFn: () => buyApi.getBuyPlans({ ...auth, panel_code: panel.code, duration: null }),
    });
    const displayMode = panel.display_mode || plansData.panel?.display_mode;
    const hasDurationStep = displayMode === "duration_first" && (plansData.durations?.length ?? 0) > 1;
    setStep(hasDurationStep ? "duration" : "plan");
  };

  const selectDuration = async (duration: number) => {
    if (!auth || !selectedPanel) return;
    haptic.select();
    setSelectedDuration(duration);
    setSelectedPlan(null);
    await queryClient.fetchQuery({
      queryKey: ["buy-plans", selectedPanel.code, duration, auth.session_token, auth.init_data],
      queryFn: () => buyApi.getBuyPlans({ ...auth, panel_code: selectedPanel.code, duration }),
    });
    setStep("plan");
  };

  const handleGenerateUsername = async () => {
    if (!selectedPanel) return;
    haptic.select();
    setFlowError("");
    try {
      const res = await generateUsername.mutateAsync(selectedPanel.code);
      if (res.username) setUsername(res.username);
      else setUsername(`VPN_${randomConfigName()}`);
    } catch {
      setUsername(`VPN_${randomConfigName()}`);
    }
  };

  const handlePreview = async () => {
    if (!selectedPanel || !selectedPlan) return;
    haptic.impact("light");
    setFlowError("");
    setPreview(null);
    try {
      const res = await previewBuy.mutateAsync({
        panelCode: selectedPanel.code,
        planId: selectedPlan.id,
        username,
        discountCode,
      });
      setPreview(res);
      setStep("confirm");
    } catch (err) {
      setFlowError((err as Error).message);
    }
  };

  const handleConfirm = async () => {
    if (!selectedPanel || !selectedPlan) return;
    haptic.impact("medium");
    setFlowError("");
    try {
      await confirmBuy.mutateAsync({
        panelCode: selectedPanel.code,
        planId: selectedPlan.id,
        username,
        discountCode,
      });
      haptic.notify("success");
      setStep("success");
    } catch (err) {
      setFlowError((err as Error).message);
    }
  };

  const resetFlow = () => {
    haptic.select();
    setStep("panel");
    setSelectedPanel(null);
    setSelectedDuration(null);
    setSelectedPlan(null);
    setUsername("");
    setDiscountCode("");
    setPreview(null);
    setFlowError("");
  };

  if (optionsLoading) {
    return (
      <div className="space-y-5">
        <BuyHeader />
        <Card className="h-32 animate-pulse bg-surface-2" />
      </div>
    );
  }

  if (optionsError || !options?.ok) {
    return (
      <div className="space-y-5">
        <BuyHeader />
        <ErrorState message={(optionsError as Error)?.message || options?.error || "خطا در بارگذاری خرید"} />
      </div>
    );
  }

  const panels = options.panels ?? [];
  const result = confirmBuy.data;

  return (
    <div className="space-y-5">
      <BuyHeader />

      <Card className="p-4">
        <div className="mb-3 flex items-center justify-between text-sm">
          <span className="text-muted">مرحله خرید</span>
          <span className="font-bold text-primary">{STEP_LABELS[stepIndex]}</span>
        </div>
        <Stepper steps={STEP_LABELS} current={stepIndex} />
      </Card>

      {flowError && <ErrorState message={flowError} />}

      <AnimatePresence mode="wait">
        {step === "panel" && (
          <motion.section key="panel" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="space-y-3">
            {panels.length === 0 ? (
              <EmptyState title="پنل فعالی برای خرید وجود ندارد." description="بعداً دوباره امتحان کنید." />
            ) : (
              panels.map((panel) => (
                <button
                  key={panel.code}
                  type="button"
                  onClick={() => void selectPanel(panel)}
                  className="group w-full overflow-hidden rounded-lg border border-border bg-surface p-4 text-right shadow-sm transition hover:-translate-y-0.5 hover:border-primary/50"
                >
                  <div className="flex items-center gap-4">
                    <div className="rounded-md bg-primary/10 p-3 text-primary ring-1 ring-primary/20">
                      <EmojiIcon id="globe_with_meridians" size={26} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="font-bold text-text">{panel.name}</p>
                      <p className="mt-1 text-xs text-muted">
                        {panel.display_mode === "duration_first" ? "اول زمان را انتخاب می‌کنی، بعد حجم" : "انتخاب سریع پلن و حجم"}
                      </p>
                    </div>
                    <span className="rounded-full bg-surface-2 px-3 py-1 text-xs text-primary ring-1 ring-border transition group-hover:bg-primary/15">
                      انتخاب
                    </span>
                  </div>
                </button>
              ))
            )}
          </motion.section>
        )}

        {step === "duration" && (
          <motion.section key="duration" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="space-y-4">
            <Button type="button" variant="ghost" size="sm" onClick={() => setStep("panel")}>
              ← بازگشت
            </Button>
            <PanelSummary panel={selectedPanel} />
            <p className="text-sm text-muted">مدت زمان سرویس را انتخاب کنید:</p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {(plansResponse?.durations ?? selectedPanel?.durations ?? []).map((duration) => (
                <button
                  key={duration}
                  type="button"
                  onClick={() => void selectDuration(duration)}
                  className="rounded-lg border border-border bg-surface p-4 text-center shadow-sm transition hover:border-primary/50 hover:bg-primary/10"
                >
                  <span className="block text-2xl font-black text-primary">{duration}</span>
                  <span className="text-xs text-muted">روز اشتراک</span>
                </button>
              ))}
            </div>
          </motion.section>
        )}

        {step === "plan" && (
          <motion.section key="plan" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="space-y-4">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() =>
                setStep(selectedPanel?.display_mode === "duration_first" ? "duration" : "panel")
              }
            >
              ← بازگشت
            </Button>
            <PanelSummary panel={selectedPanel} duration={selectedDuration} />
            {plansLoading ? (
              <Card className="h-24 animate-pulse bg-surface-2" />
            ) : (
              <div className="grid gap-3 sm:grid-cols-2">
                {plansForDuration.map((plan) => (
                  <button
                    key={plan.id}
                    type="button"
                    onClick={() => {
                      haptic.select();
                      setSelectedPlan(plan);
                      setStep("username");
                    }}
                    className="group w-full overflow-hidden rounded-lg border border-border bg-surface p-4 text-right shadow-sm transition hover:-translate-y-0.5 hover:border-primary/50"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-lg font-black text-text">{plan.plan_name}</p>
                        <p className="mt-1 text-xs text-muted">
                          {plan.duration} روزه {plan.ip_limit > 0 ? `• ${plan.ip_limit} کاربر` : "• نامحدود کاربر"}
                        </p>
                      </div>
                      <span className="rounded-md bg-primary/10 px-3 py-2 text-sm font-bold text-primary ring-1 ring-primary/20">
                        {formatNumber(plan.price)}
                      </span>
                    </div>
                    <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-surface-2">
                      <div className="h-full w-2/3 rounded-full bg-primary transition group-hover:w-full" />
                    </div>
                  </button>
                ))}
              </div>
            )}
          </motion.section>
        )}

        {step === "username" && selectedPlan && (
          <motion.section key="username" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="space-y-4">
            <Button type="button" variant="ghost" size="sm" onClick={() => setStep("plan")}>
              ← بازگشت
            </Button>
            <PlanSummary plan={selectedPlan} />
            <Input
              label="نام کانفیگ"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="مثال: Amir_123"
              ltr
            />
            <p className="text-xs text-muted">فقط حروف انگلیسی، عدد و زیرخط مجاز است.</p>
            <Button type="button" variant="secondary" loading={generateUsername.isPending} onClick={() => void handleGenerateUsername()}>
              <EmojiIcon id="sparkles" size={16} />
              ساخت نام تصادفی
            </Button>
            <Input
              label="کد تخفیف (اختیاری)"
              value={discountCode}
              onChange={(e) => setDiscountCode(e.target.value)}
              placeholder="کد تخفیف"
              ltr
            />
            <Button type="button" fullWidth loading={previewBuy.isPending} disabled={username.trim().length < 3} onClick={() => void handlePreview()}>
              بررسی و ادامه
            </Button>
          </motion.section>
        )}

        {step === "confirm" && selectedPlan && preview && (
          <motion.section key="confirm" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="space-y-4">
            <Button type="button" variant="ghost" size="sm" onClick={() => setStep("username")}>
              ← بازگشت
            </Button>
            <Card className="space-y-3 border-primary/20 p-4">
              <PlanSummary plan={selectedPlan} />
              <InfoRow label="نام کانفیگ" value={preview.username ?? username} />
              <InfoRow label="موجودی فعلی" value={formatToman(preview.balance ?? 0)} />
              <InfoRow label="قیمت اصلی" value={formatToman(preview.base_price ?? 0)} />
              {preview.discount_percent ? <InfoRow label="تخفیف" value={`${preview.discount_percent}%`} /> : null}
              <Card className="bg-primary/10 p-3 ring-1 ring-primary/20">
                <InfoRow label="مبلغ نهایی" value={formatToman(preview.final_price ?? 0)} strong />
              </Card>
              <InfoRow label="موجودی بعد از خرید" value={formatToman(preview.balance_after ?? 0)} />
            </Card>
            {(preview.locations?.length ?? 0) > 0 && (
              <Card className="p-4">
                <p className="mb-2 text-sm text-muted">لوکیشن‌های این پلن</p>
                <p className="text-sm leading-7 text-text">{preview.locations.join(" ⌁ ")}</p>
              </Card>
            )}
            {!preview.can_pay && (
              <p className="rounded-md border border-danger/25 bg-danger/5 px-4 py-3 text-sm text-danger">
                موجودی برای این خرید کافی نیست. ابتدا کیف پول را شارژ کنید.
              </p>
            )}
            <Button type="button" fullWidth loading={confirmBuy.isPending} disabled={!preview.can_pay} onClick={() => void handleConfirm()}>
              تأیید و خرید
            </Button>
          </motion.section>
        )}

        {step === "success" && result && (
          <motion.section key="success" initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className="space-y-4">
            <Card className="border-success/30 bg-success/5 p-4">
              <p className="flex items-center gap-2 font-semibold text-success">
                <EmojiIcon id="white_check_mark" size={24} />
                {result.message ?? "خرید با موفقیت انجام شد"}
              </p>
            </Card>
            <Card className="space-y-3 p-4">
              <InfoRow label="کد سرویس" value={String(result.service_code ?? "-")} />
              <InfoRow label="نام کانفیگ" value={result.username ?? "-"} />
              <InfoRow label="پنل" value={result.panel_name ?? "-"} />
              <InfoRow label="حجم" value={result.volume ?? "-"} />
              <InfoRow label="مدت" value={`${result.duration ?? "-"} روز`} />
              <InfoRow label="مبلغ پرداختی" value={formatToman(result.amount_paid ?? 0)} strong />
              <InfoRow label="موجودی جدید" value={formatToman(result.new_balance ?? 0)} />
            </Card>
            {result.subscription_url && (
              <Card className="space-y-3 p-4">
                <p className="text-sm text-muted">لینک سابسکریپشن</p>
                <p className="break-all font-mono text-xs text-text" dir="ltr">
                  {result.subscription_url}
                </p>
                <Button type="button" variant="secondary" onClick={() => void copyToClipboard(result.subscription_url!)}>
                  کپی لینک
                </Button>
              </Card>
            )}
            {result.single_config_links_text && (
              <Card className="p-4">
                <p className="mb-2 text-sm text-muted">لینک‌های تکی</p>
                <p className="whitespace-pre-wrap break-all text-xs text-text" dir="ltr">
                  {result.single_config_links_text}
                </p>
              </Card>
            )}
            <Button type="button" fullWidth onClick={resetFlow}>
              خرید سرویس دیگر
            </Button>
          </motion.section>
        )}
      </AnimatePresence>
    </div>
  );
}

function BuyHeader() {
  return (
    <header className="relative overflow-hidden rounded-lg border border-accent/20 bg-surface p-5 shadow-md">
      <div className="absolute -left-14 -top-14 h-36 w-36 rounded-full bg-accent/15 blur-3xl" />
      <div className="relative flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.3em] text-accent/70">Premium Config</p>
          <h1 className="mt-2 text-2xl font-black text-text">خرید سرویس اختصاصی</h1>
          <p className="mt-2 max-w-lg text-sm leading-7 text-muted">
            پلن، مدت، نام کانفیگ و کد تخفیف را همین‌جا انتخاب کن؛ قبل از خرید قیمت نهایی و موجودی بعد از پرداخت را می‌بینی.
          </p>
        </div>
        <div className="rounded-md border border-border bg-surface-2 p-3 text-accent">
          <EmojiIcon id="shopping_cart" size={30} />
        </div>
      </div>
    </header>
  );
}
