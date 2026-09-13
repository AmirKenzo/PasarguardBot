import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button, Card, SkeletonCard } from "../../components/ui";
import { ErrorState } from "../../components/ui/EmptyState";
import { useTelegram } from "../../hooks/useTelegram";
import { formatBytes, formatToman } from "../../lib/format";
import { useExtraVolumeConfirmMutation, useExtraVolumeOptionsQuery } from "../../queries/useServices";
import type { VolumePlanItem } from "../../types/webapp";

type Step = "plan" | "success";

export default function ExtraVolumeFlow() {
  const { t } = useTranslation();
  const { code: codeParam } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const { haptic } = useTelegram();

  const code = codeParam ? Number(codeParam) : null;
  const { data, isLoading, error, refetch } = useExtraVolumeOptionsQuery(code);
  const confirm = useExtraVolumeConfirmMutation();

  const [step, setStep] = useState<Step>("plan");
  const [submitError, setSubmitError] = useState("");

  const backTo = code != null ? `/services/${code}` : "/services";

  if (code == null || Number.isNaN(code)) {
    return (
      <div>
        <PageHeader title={t("extraVolume.title")} back="/services" />
        <ErrorState message={t("renewFlow.invalidCode")} />
      </div>
    );
  }

  if (isLoading) {
    return (
      <div>
        <PageHeader title={t("extraVolume.title")} back={backTo} />
        <SkeletonCard />
      </div>
    );
  }

  if (error || !data?.plans?.length) {
    return (
      <div>
        <PageHeader title={t("extraVolume.title")} back={backTo} />
        <ErrorState
          message={(error as Error)?.message || data?.error || t("extraVolume.noPlans")}
          onRetry={() => void refetch()}
        />
      </div>
    );
  }

  const handleSelect = (plan: VolumePlanItem) => {
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
      <PageHeader title={t("extraVolume.title")} subtitle={data.panel_name ?? undefined} back={backTo} />

      <AnimatePresence mode="wait">
        {step === "plan" && (
          <motion.div key="plan" initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }} className="space-y-3">
            <p className="text-sm text-muted">{t("extraVolume.selectPlan")}</p>
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
                    <p className="font-semibold text-text">{formatBytes(plan.storage_gb * 1024 ** 3)}</p>
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
              <p className="font-semibold text-success">{t("extraVolume.success")}</p>
              {confirm.data?.added_bytes != null && (
                <p className="text-sm text-text">
                  {t("extraVolume.addedVolume")}: <span className="font-semibold">{formatBytes(confirm.data.added_bytes)}</span>
                </p>
              )}
              {confirm.data?.new_total_traffic_bytes != null && (
                <p className="text-sm text-text">
                  {t("extraVolume.newTotalVolume")}:{" "}
                  <span className="font-semibold">{formatBytes(confirm.data.new_total_traffic_bytes)}</span>
                </p>
              )}
              {confirm.data?.amount_paid != null && (
                <p className="text-sm text-text">
                  {t("extraVolume.amountPaid")}: <span className="font-semibold">{formatToman(confirm.data.amount_paid)}</span>
                </p>
              )}
              {confirm.data?.new_balance != null && (
                <p className="text-sm text-text">
                  {t("extraVolume.newBalance")}: <span className="font-semibold">{formatToman(confirm.data.new_balance)}</span>
                </p>
              )}
            </Card>
            <Button type="button" fullWidth onClick={() => navigate(backTo)}>
              {t("extraVolume.backToService")}
            </Button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
