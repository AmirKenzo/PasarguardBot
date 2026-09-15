import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button, Card, Input, SkeletonCard } from "../../components/ui";
import { ErrorState } from "../../components/ui/EmptyState";
import { useTelegram } from "../../hooks/useTelegram";
import { formatBytes, formatToman } from "../../lib/format";
import { formatPlanLabel } from "../../lib/serviceHelpers";
import { useRenewConfirmMutation, useRenewOptionsQuery } from "../../queries/useServices";
import type { RenewPlanItem } from "../../types/webapp";

type RenewStep = "duration" | "plan" | "confirm" | "success";

export default function RenewFlow() {
  const { t } = useTranslation();
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

  const durationOptions = useMemo(() => {
    const durations = data?.durations ?? [];
    return [...durations].sort((a, b) => a - b);
  }, [data?.durations]);

  const hasDurationStep = durationOptions.length > 0;

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
        <PageHeader title={t("renewFlow.title")} back="/services" />
        <ErrorState message={t("renewFlow.invalidCode")} />
      </div>
    );
  }

  if (isLoading) {
    return (
      <div>
        <PageHeader title={t("renewFlow.title")} back={backTo} />
        <SkeletonCard />
      </div>
    );
  }

  if (error || !data?.plans?.length) {
    return (
      <div>
        <PageHeader title={t("renewFlow.title")} back={backTo} />
        <ErrorState
          message={(error as Error)?.message || data?.error || t("renewFlow.noPlans")}
          onRetry={() => void refetch()}
        />
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
      <PageHeader title={t("renewFlow.title")} subtitle={data.panel_name ?? undefined} back={backTo} />

      <AnimatePresence mode="wait">
        {step === "duration" && hasDurationStep && (
          <motion.div key="duration" initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }} className="space-y-3">
            <p className="text-sm text-muted">{t("renewFlow.selectDuration")}</p>
            <div className="flex flex-wrap gap-2">
              {durationOptions.map((duration) => (
                <Button
                  key={duration}
                  type="button"
                  variant="secondary"
                  onClick={() => {
                    haptic.select();
                    setSelectedDuration(duration);
                    setStep("plan");
                  }}
                >
                  {t("renewFlow.days", { count: duration })}
                </Button>
              ))}
            </div>
          </motion.div>
        )}

        {step === "plan" && (
          <motion.div key="plan" initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }} className="space-y-3">
            {hasDurationStep && (
              <Button type="button" variant="ghost" size="sm" onClick={() => setStep("duration")}>
                {t("buy.back")}
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
                    <p className="font-semibold text-text">
                      {formatPlanLabel(plan.storage, plan.plan_type, plan.data_limit_reset_strategy, true)}
                    </p>
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
              {t("buy.back")}
            </Button>
            <Card className="space-y-2 p-4">
              <p className="font-semibold text-text">
                {formatPlanLabel(selectedPlan.storage, selectedPlan.plan_type, selectedPlan.data_limit_reset_strategy, true)}
              </p>
              <p className="text-xs text-muted">
                {t("renewFlow.days", { count: selectedPlan.duration })} · {formatToman(selectedPlan.price)}
              </p>
            </Card>
            <Input
              label={t("renewFlow.discountCode")}
              value={discountCode}
              onChange={(e) => setDiscountCode(e.target.value)}
              placeholder={t("renewFlow.discountCodePlaceholder")}
              ltr
              disabled={confirmRenew.isPending}
            />
            {submitError && <p className="text-sm text-danger">{submitError}</p>}
            <Button type="button" fullWidth loading={confirmRenew.isPending} onClick={handleConfirm}>
              {t("renewFlow.confirmAndRenew")}
            </Button>
          </motion.div>
        )}

        {step === "success" && (
          <motion.div key="success" initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className="space-y-4">
            <Card className="space-y-2 border-success/30 bg-success/5 p-4">
              <p className="font-semibold text-success">{confirmRenew.data?.message ?? t("renewFlow.renewSuccess")}</p>
              {confirmRenew.data?.new_volume_bytes != null && (
                <p className="text-sm text-text">
                  {t("renewFlow.newVolume")}: <span className="font-semibold">{formatBytes(confirmRenew.data.new_volume_bytes)}</span>
                </p>
              )}
              {confirmRenew.data?.amount_paid != null && (
                <p className="text-sm text-text">
                  {t("renewFlow.amountPaid")}: <span className="font-semibold">{formatToman(confirmRenew.data.amount_paid)}</span>
                </p>
              )}
              {confirmRenew.data?.new_balance != null && (
                <p className="text-sm text-text">
                  {t("renewFlow.newBalance")}: <span className="font-semibold">{formatToman(confirmRenew.data.new_balance)}</span>
                </p>
              )}
            </Card>
            <Button type="button" fullWidth onClick={() => navigate(backTo)}>
              {t("renewFlow.backToService")}
            </Button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
