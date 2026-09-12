import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button, Card, Input, SkeletonCard } from "../../components/ui";
import { ErrorState } from "../../components/ui/EmptyState";
import { useTelegram } from "../../hooks/useTelegram";
import { formatNumber, formatToman } from "../../lib/format";
import { useRenewConfirmMutation, useRenewOptionsQuery } from "../../queries/useServices";
import type { RenewPlanItem } from "../../types/webapp";

type RenewStep = "duration" | "plan" | "confirm" | "success";

export default function RenewFlow() {
  const { code: codeParam } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const { haptic } = useTelegram();

  const code = codeParam ? Number(codeParam) : null;
  const { data, isLoading, error, refetch } = useRenewOptionsQuery(code);
  const confirmRenew = useRenewConfirmMutation();

  const [step, setStep] = useState<RenewStep>("duration");
  const [selectedDuration, setSelectedDuration] = useState<number | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<RenewPlanItem | null>(null);
  const [discountCode, setDiscountCode] = useState("");
  const [submitError, setSubmitError] = useState("");

  const hasDurationStep = useMemo(() => {
    const groups = data?.duration_groups;
    return groups != null && Object.keys(groups).length > 0;
  }, [data?.duration_groups]);

  useEffect(() => {
    if (!data?.plans?.length) return;
    if (hasDurationStep) {
      setStep("duration");
      return;
    }
    const firstPlan = data.plans[0];
    if (firstPlan) setSelectedDuration(firstPlan.duration);
    setStep("plan");
  }, [data?.plans, hasDurationStep]);

  const plansForStep = useMemo(() => {
    const plans = data?.plans ?? [];
    if (selectedDuration == null) return plans;
    return plans.filter((p) => p.duration === selectedDuration);
  }, [data?.plans, selectedDuration]);

  const backTo = code != null ? `/services/${code}` : "/services";

  if (code == null || Number.isNaN(code)) {
    return (
      <div>
        <PageHeader title="تمدید سرویس" back="/services" />
        <ErrorState message="کد سرویس نامعتبر است" />
      </div>
    );
  }

  if (isLoading) {
    return (
      <div>
        <PageHeader title="تمدید سرویس" back={backTo} />
        <SkeletonCard />
      </div>
    );
  }

  if (error || !data?.plans?.length) {
    return (
      <div>
        <PageHeader title="تمدید سرویس" back={backTo} />
        <ErrorState message={(error as Error)?.message || data?.error || "پلنی یافت نشد"} onRetry={() => void refetch()} />
      </div>
    );
  }

  const handleConfirm = () => {
    if (!selectedPlan) return;
    haptic.impact("medium");
    setSubmitError("");
    confirmRenew.mutate(
      { code, planId: selectedPlan.id, discountCode },
      {
        onSuccess: () => {
          haptic.notify("success");
          setStep("success");
        },
        onError: (err) => setSubmitError((err as Error).message),
      }
    );
  };

  return (
    <div>
      <PageHeader title="تمدید سرویس" subtitle={data.panel_name ?? undefined} back={backTo} />

      <AnimatePresence mode="wait">
        {step === "duration" && data.duration_groups && (
          <motion.div key="duration" initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }} className="space-y-3">
            <p className="text-sm text-muted">مدت زمان را انتخاب کنید:</p>
            <div className="flex flex-wrap gap-2">
              {Object.entries(data.duration_groups).map(([label, durs]) => (
                <Button
                  key={label}
                  type="button"
                  variant="secondary"
                  onClick={() => {
                    haptic.select();
                    setSelectedDuration(durs[0] ?? null);
                    setStep("plan");
                  }}
                >
                  {label}
                </Button>
              ))}
            </div>
          </motion.div>
        )}

        {step === "plan" && (
          <motion.div key="plan" initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }} className="space-y-3">
            {hasDurationStep && (
              <Button type="button" variant="ghost" size="sm" onClick={() => setStep("duration")}>
                ← بازگشت
              </Button>
            )}
            <div className="max-h-[50vh] space-y-2 overflow-y-auto">
              {plansForStep.map((plan) => (
                <button
                  key={plan.id}
                  type="button"
                  onClick={() => {
                    haptic.select();
                    setSelectedPlan(plan);
                    setStep("confirm");
                  }}
                  className="w-full rounded-lg border border-border bg-surface p-4 text-right shadow-sm transition hover:-translate-y-0.5 hover:border-primary/50"
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-semibold text-text">{plan.plan_name}</p>
                    <span className="rounded-md bg-primary/10 px-3 py-1.5 text-xs font-bold text-primary ring-1 ring-primary/20">
                      {formatToman(plan.price)}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </motion.div>
        )}

        {step === "confirm" && selectedPlan && (
          <motion.div key="confirm" initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }} className="space-y-4">
            <Button type="button" variant="ghost" size="sm" onClick={() => setStep("plan")}>
              ← بازگشت
            </Button>
            <Card className="space-y-2 p-4">
              <p className="font-semibold text-text">{selectedPlan.plan_name}</p>
              <p className="text-xs text-muted">
                {selectedPlan.duration} روز · {formatToman(selectedPlan.price)}
              </p>
            </Card>
            <Input
              label="کد تخفیف (اختیاری)"
              value={discountCode}
              onChange={(e) => setDiscountCode(e.target.value)}
              placeholder="کد تخفیف"
              ltr
              disabled={confirmRenew.isPending}
            />
            {submitError && <p className="text-sm text-danger">{submitError}</p>}
            <Button type="button" fullWidth loading={confirmRenew.isPending} onClick={handleConfirm}>
              تأیید و تمدید
            </Button>
          </motion.div>
        )}

        {step === "success" && (
          <motion.div key="success" initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className="space-y-4">
            <Card className="space-y-2 border-success/30 bg-success/5 p-4">
              <p className="font-semibold text-success">{confirmRenew.data?.message ?? "تمدید با موفقیت انجام شد"}</p>
              {confirmRenew.data?.new_volume && (
                <p className="text-sm text-text">
                  حجم جدید: <span className="font-semibold">{confirmRenew.data.new_volume}</span>
                </p>
              )}
              {confirmRenew.data?.amount_paid != null && (
                <p className="text-sm text-text">
                  مبلغ پرداختی: <span className="font-semibold">{formatToman(confirmRenew.data.amount_paid)}</span>
                </p>
              )}
              {confirmRenew.data?.new_balance != null && (
                <p className="text-sm text-text">
                  موجودی جدید: <span className="font-semibold">{formatNumber(confirmRenew.data.new_balance)} تومان</span>
                </p>
              )}
            </Card>
            <Button type="button" fullWidth onClick={() => navigate(backTo)}>
              بازگشت به سرویس
            </Button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
