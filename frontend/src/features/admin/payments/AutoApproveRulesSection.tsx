import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Input } from "../../../components/ui";
import { panelPaymentsApi } from "../../../api/panel";
import type { PanelAutoApproveRuleRow } from "../../../types/panel";
import { usePanelAction } from "../../../queries/usePanelApi";
import { ConfirmButton, DataTable, SectionCard } from "../components";
import type { Column } from "../components";
import { PAYMENTS_INVALIDATE } from "./shared";

const EMPTY_RULE = { min: "0", max: "", delay: "30" };

interface AutoApproveRulesSectionProps {
  rules: PanelAutoApproveRuleRow[];
}

export default function AutoApproveRulesSection({ rules }: AutoApproveRulesSectionProps) {
  const { t } = useTranslation();
  const createRule = usePanelAction(panelPaymentsApi.createRule, { invalidate: PAYMENTS_INVALIDATE });
  const toggleRule = usePanelAction(panelPaymentsApi.toggleRule, { invalidate: PAYMENTS_INVALIDATE });
  const deleteRule = usePanelAction(panelPaymentsApi.deleteRule, { invalidate: PAYMENTS_INVALIDATE });
  const [rule, setRule] = useState(EMPTY_RULE);

  const ruleColumns: Column<PanelAutoApproveRuleRow>[] = [
    { key: "range", header: t("panel.payments.successfulRange"), cell: (row) => t("panel.payments.txRange", { from: row.min_successful_tx, to: row.max_successful_tx ?? "∞" }) },
    { key: "delay", header: t("panel.payments.approvalDelay"), cell: (row) => t("panel.payments.delayMinutes", { count: row.auto_approve_delay_minutes }) },
    {
      key: "status",
      header: t("panel.common.status"),
      cell: (row) => (row.is_active ? <Badge tone="success">{t("panel.common.active")}</Badge> : <Badge tone="muted">{t("panel.common.inactive")}</Badge>),
    },
    {
      key: "actions",
      header: "",
      cell: (row) => (
        <div className="flex gap-1.5">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => toggleRule.mutate({ rule_id: row.id, is_active: !row.is_active })}
          >
            {row.is_active ? t("panel.common.inactive") : t("panel.common.active")}
          </Button>
          <ConfirmButton
            size="sm"
            variant="danger"
            message={t("panel.payments.ruleDeleteConfirm")}
            onConfirm={() => deleteRule.mutate({ rule_id: row.id })}
          >
            {t("common.delete")}
          </ConfirmButton>
        </div>
      ),
    },
  ];

  return (
    <SectionCard
      title={t("panel.common.autoApproveCardTransfer")}
      description={t("panel.payments.ruleBasis")}
    >
      <DataTable columns={ruleColumns} rows={rules} rowKey={(row) => row.id} emptyTitle={t("panel.payments.rulesEmpty")} />
      <div className="mt-4 grid gap-3 border-t border-border pt-4 sm:grid-cols-3">
        <Input
          label={t("panel.payments.minSuccessful")}
          inputMode="numeric"
          value={rule.min}
          onChange={(event) => setRule((prev) => ({ ...prev, min: event.target.value }))}
        />
        <Input
          label={t("panel.payments.maxOrUnlimited")}
          inputMode="numeric"
          value={rule.max}
          onChange={(event) => setRule((prev) => ({ ...prev, max: event.target.value }))}
        />
        <Input
          label={t("panel.payments.approvalDelayMinutes")}
          inputMode="numeric"
          value={rule.delay}
          onChange={(event) => setRule((prev) => ({ ...prev, delay: event.target.value }))}
        />
        <div className="flex items-end">
          <Button
            loading={createRule.isPending}
            onClick={() =>
              createRule.mutate(
                {
                  min_successful_tx: Number(rule.min) || 0,
                  max_successful_tx: rule.max.trim() ? Number(rule.max) : null,
                  auto_approve_delay_minutes: Number(rule.delay) || 0,
                },
                { onSuccess: () => setRule(EMPTY_RULE) }
              )
            }
          >
            {t("panel.payments.addRule")}
          </Button>
        </div>
      </div>
    </SectionCard>
  );
}
