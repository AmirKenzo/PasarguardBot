import { useState } from "react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge, Button, ErrorState, Input, Skeleton } from "../../components/ui";
import { panelPaymentsApi } from "../../api/panel";
import type { PanelAutoApproveRuleRow, PanelCardRow, PanelWalletRow } from "../../types/panel";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { ConfirmButton, DataTable, SectionCard, SelectField, Toggle } from "./components";
import type { Column } from "./components";
import { useTranslation } from "react-i18next";

const INVALIDATE = [["payments"]];

export default function AdminPaymentsPage() {
  const { t } = useTranslation();
  const query = usePanelQuery(["payments"], (auth) => panelPaymentsApi.getPayments(auth));

  const createWallet = usePanelAction(panelPaymentsApi.createWallet, { invalidate: INVALIDATE });
  const deleteWallet = usePanelAction(panelPaymentsApi.deleteWallet, { invalidate: INVALIDATE });
  const createCard = usePanelAction(panelPaymentsApi.createCard, { invalidate: INVALIDATE });
  const activateCard = usePanelAction(panelPaymentsApi.activateCard, { invalidate: INVALIDATE });
  const deleteCard = usePanelAction(panelPaymentsApi.deleteCard, { invalidate: INVALIDATE });
  const createRule = usePanelAction(panelPaymentsApi.createRule, { invalidate: INVALIDATE });
  const toggleRule = usePanelAction(panelPaymentsApi.toggleRule, { invalidate: INVALIDATE });
  const deleteRule = usePanelAction(panelPaymentsApi.deleteRule, { invalidate: INVALIDATE });

  const [wallet, setWallet] = useState({ wallet_type: "", address: "", api_key: "" });
  const [card, setCard] = useState({ number: "", name: "", active: true });
  const [rule, setRule] = useState({ min: "0", max: "", delay: "30" });

  if (query.isLoading) {
    return <Skeleton className="h-64 w-full" />;
  }
  if (query.isError || !query.data) {
    return <ErrorState message={query.error?.message || t("common.error")} onRetry={() => void query.refetch()} />;
  }

  const { wallets, available_wallet_types: availableTypes, cards, rules } = query.data;

  const walletColumns: Column<PanelWalletRow>[] = [
    { key: "type", header: t("panel.payments.currency"), cell: (row) => <Badge tone="primary">{row.type}</Badge> },
    {
      key: "address",
      header: t("panel.common.address"),
      cell: (row) => <span className="ltr-field break-all text-xs">{row.address}</span>,
    },
    {
      key: "api",
      header: "API Key",
      secondary: true,
      cell: (row) => (row.has_api_key ? <Badge tone="success">{t("panel.payments.present")}</Badge> : <span className="text-xs text-muted">—</span>),
    },
    {
      key: "actions",
      header: "",
      cell: (row) => (
        <ConfirmButton
          size="sm"
          variant="danger"
          message={t("panel.payments.walletDeleteConfirm", { type: row.type })}
          onConfirm={() => deleteWallet.mutate({ wallet_id: row.id })}
        >
          {t("common.delete")}
        </ConfirmButton>
      ),
    },
  ];

  const cardColumns: Column<PanelCardRow>[] = [
    { key: "number", header: t("panel.payments.cardNumberPlain"), cell: (row) => <span className="ltr-field text-xs">{row.number}</span> },
    { key: "name", header: t("panel.payments.cardHolder"), cell: (row) => row.name },
    {
      key: "status",
      header: t("panel.common.status"),
      cell: (row) => (row.active ? <Badge tone="success">{t("panel.common.active")}</Badge> : <Badge tone="muted">{t("panel.common.inactive")}</Badge>),
    },
    {
      key: "actions",
      header: "",
      cell: (row) => (
        <div className="flex gap-1.5">
          {!row.active && (
            <Button size="sm" variant="ghost" onClick={() => activateCard.mutate({ card_id: row.id })}>
              {t("panel.payments.enable")}
            </Button>
          )}
          <ConfirmButton
            size="sm"
            variant="danger"
            message={t("panel.payments.cardDeleteConfirm")}
            onConfirm={() => deleteCard.mutate({ card_id: row.id })}
          >
            {t("common.delete")}
          </ConfirmButton>
        </div>
      ),
    },
  ];

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
    <>
      <PageHeader title={t("panel.common.paymentGateways")} subtitle={t("panel.payments.subtitle")} />

      <SectionCard title={t("panel.payments.cryptoWallets")}>
        <DataTable columns={walletColumns} rows={wallets} rowKey={(row) => row.id} emptyTitle={t("panel.payments.walletsEmpty")} />
        {availableTypes.length > 0 && (
          <div className="mt-4 grid gap-3 border-t border-border pt-4 sm:grid-cols-2">
            <SelectField
              label={t("panel.payments.currency")}
              options={[{ value: "", label: t("panel.common.choose") }, ...availableTypes.map((type) => ({ value: type, label: type }))]}
              value={wallet.wallet_type}
              onChange={(event) => setWallet((prev) => ({ ...prev, wallet_type: event.target.value }))}
            />
            <Input
              label={t("panel.payments.walletAddress")}
              ltr
              value={wallet.address}
              onChange={(event) => setWallet((prev) => ({ ...prev, address: event.target.value }))}
            />
            <Input
              label={t("panel.payments.apiKey")}
              ltr
              value={wallet.api_key}
              onChange={(event) => setWallet((prev) => ({ ...prev, api_key: event.target.value }))}
            />
            <div className="flex items-end">
              <Button
                loading={createWallet.isPending}
                disabled={!wallet.wallet_type || wallet.address.trim().length < 4}
                onClick={() =>
                  createWallet.mutate(wallet, {
                    onSuccess: () => setWallet({ wallet_type: "", address: "", api_key: "" }),
                  })
                }
              >
                {t("panel.common.addWallet")}
              </Button>
            </div>
          </div>
        )}
      </SectionCard>

      <SectionCard title={t("panel.payments.manualCards")}>
        <DataTable columns={cardColumns} rows={cards} rowKey={(row) => row.id} emptyTitle={t("panel.payments.cardsEmpty")} />
        <div className="mt-4 grid gap-3 border-t border-border pt-4 sm:grid-cols-2">
          <Input
            label={t("panel.payments.cardNumber")}
            ltr
            inputMode="numeric"
            value={card.number}
            onChange={(event) => setCard((prev) => ({ ...prev, number: event.target.value }))}
          />
          <Input
            label={t("panel.payments.cardHolder")}
            value={card.name}
            onChange={(event) => setCard((prev) => ({ ...prev, name: event.target.value }))}
          />
          <Toggle
            checked={card.active}
            onChange={(active) => setCard((prev) => ({ ...prev, active }))}
            label={t("panel.payments.activeNow")}
            hint={t("panel.payments.activeCardNote")}
          />
          <div className="flex items-end">
            <Button
              loading={createCard.isPending}
              disabled={card.number.replace(/\D/g, "").length < 12 || !card.name.trim()}
              onClick={() =>
                createCard.mutate(card, { onSuccess: () => setCard({ number: "", name: "", active: true }) })
              }
            >
              {t("panel.common.addCard")}
            </Button>
          </div>
        </div>
      </SectionCard>

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
                  { onSuccess: () => setRule({ min: "0", max: "", delay: "30" }) }
                )
              }
            >
              {t("panel.payments.addRule")}
            </Button>
          </div>
        </div>
      </SectionCard>
    </>
  );
}
