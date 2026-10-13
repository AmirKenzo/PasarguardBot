import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Input } from "../../../components/ui";
import { panelPaymentsApi } from "../../../api/panel";
import type { PanelCardRow } from "../../../types/panel";
import { usePanelAction } from "../../../queries/usePanelApi";
import { ConfirmButton, DataTable, SectionCard, Toggle } from "../components";
import type { Column } from "../components";
import { PAYMENTS_INVALIDATE } from "./shared";

const EMPTY_CARD = { number: "", name: "", active: true };

interface ManualCardsSectionProps {
  cards: PanelCardRow[];
}

export default function ManualCardsSection({ cards }: ManualCardsSectionProps) {
  const { t } = useTranslation();
  const createCard = usePanelAction(panelPaymentsApi.createCard, { invalidate: PAYMENTS_INVALIDATE });
  const activateCard = usePanelAction(panelPaymentsApi.activateCard, { invalidate: PAYMENTS_INVALIDATE });
  const deleteCard = usePanelAction(panelPaymentsApi.deleteCard, { invalidate: PAYMENTS_INVALIDATE });
  const [card, setCard] = useState(EMPTY_CARD);
  const cardReady = card.number.replace(/\D/g, "").length >= 12 && card.name.trim() !== "";

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

  return (
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
            disabled={!cardReady}
            onClick={() => createCard.mutate(card, { onSuccess: () => setCard(EMPTY_CARD) })}
          >
            {t("panel.common.addCard")}
          </Button>
        </div>
        {!cardReady && <p className="text-xs text-muted sm:col-span-2">{t("panel.payments.cardRequiredHint")}</p>}
      </div>
    </SectionCard>
  );
}
