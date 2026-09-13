import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button, Card, SkeletonCard } from "../../components/ui";
import { ErrorState } from "../../components/ui/EmptyState";
import { useTelegram } from "../../hooks/useTelegram";
import { formatExpiry, formatToman } from "../../lib/format";
import { useExtendTimeConfirmMutation, useExtendTimeOptionsQuery } from "../../queries/useServices";
import type { TimePlanItem } from "../../types/webapp";

type Step = "plan" | "success";

export default function ExtendTimeFlow() {
  const { t } = useTranslation();
  const { code: codeParam } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const { haptic } = useTelegram();

  const code = codeParam ? Number(codeParam) : null;
  const { data, isLoading, error, refetch } = useExtendTimeOptionsQuery(code);
  const confirm = useExtendTimeConfirmMutation();

  const [step, setStep] = useState<Step>("plan");
  const [submitError, setSubmitError] = useState("");

  const backTo = code != null ? `/services/${code}` : "/services";

  if (code == null || Number.isNaN(code)) {
    return (
      <div>
        <PageHeader title={t("extendTime.title")} back="/services" />
        <ErrorState message={t("renewFlow.invalidCode")} />
      </div>
    );
  }

  if (isLoading) {
    return (
      <div>
        <PageHeader title={t("extendTime.title")} back={backTo} />
        <SkeletonCard />
      </div>
    );
  }

  if (error || !data?.plans?.length) {
    return (
      <div>
        <PageHeader title={t("extendTime.title")} back={backTo} />
        <ErrorState
          message={(error as Error)?.message || data?.error || t("extendTime.noPlans")}
          onRetry={() => void refetch()}
        />
      </div>
    );
  }

  const handleSelect = (plan: TimePlanItem) => {
    haptic.impact("medium");
    setSubmitError("");
    confirm.mutate(
      { code, planId: plan.id },
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
      <PageHeader title={t("extendTime.title")} subtitle={data.panel_name ?? undefined} back={backTo} />

      <AnimatePresence mode="wait">
        {step === "plan" && (
          <motion.div key="plan" initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }} className="space-y-3">
            <p className="text-sm text-muted">{t("extendTime.selectPlan")}</p>
            {submitError && <p className="text-sm text-danger">{submitError}</p>}
            <div className="max-h-[60vh] space-y-2 overflow-y-auto">
              {data.plans.map((plan) => (
                <button
                  key={plan.id}
                  type="button"
                  disabled={confirm.isPending}
                  onClick={() => handleSelect(plan)}
                  className="w-full rounded-lg border border-border bg-surface p-4 text-right shadow-sm transition hover:-translate-y-0.5 hover:border-primary/50 disabled:opacity-50"
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-semibold text-text">{t("renewFlow.days", { count: plan.duration_days })}</p>
                    <span className="rounded-md bg-primary/10 px-3 py-1.5 text-xs font-bold text-primary ring-1 ring-primary/20">
                      {formatToman(plan.price)}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </motion.div>
        )}

        {step === "success" && (
          <motion.div key="success" initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className="space-y-4">
            <Card className="space-y-2 border-success/30 bg-success/5 p-4">
              <p className="font-semibold text-success">{t("extendTime.success")}</p>
              {confirm.data?.added_days != null && (
                <p className="text-sm text-text">
                  {t("extendTime.addedTime")}: <span className="font-semibold">{t("renewFlow.days", { count: confirm.data.added_days })}</span>
                </p>
              )}
              {confirm.data?.new_expiration_timestamp != null && (
                <p className="text-sm text-text">
                  {t("extendTime.newExpiry")}:{" "}
                  <span className="font-semibold">{formatExpiry(confirm.data.new_expiration_timestamp).date}</span>
                </p>
              )}
              {confirm.data?.amount_paid != null && (
                <p className="text-sm text-text">
                  {t("extendTime.amountPaid")}: <span className="font-semibold">{formatToman(confirm.data.amount_paid)}</span>
                </p>
              )}
              {confirm.data?.new_balance != null && (
                <p className="text-sm text-text">
                  {t("extendTime.newBalance")}: <span className="font-semibold">{formatToman(confirm.data.new_balance)}</span>
                </p>
              )}
            </Card>
            <Button type="button" fullWidth onClick={() => navigate(backTo)}>
              {t("extendTime.backToService")}
            </Button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
