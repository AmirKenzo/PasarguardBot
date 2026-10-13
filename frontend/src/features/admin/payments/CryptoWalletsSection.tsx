import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Input } from "../../../components/ui";
import { panelPaymentsApi } from "../../../api/panel";
import type { PanelWalletRow } from "../../../types/panel";
import { usePanelAction } from "../../../queries/usePanelApi";
import { ConfirmButton, DataTable, SectionCard, SelectField } from "../components";
import type { Column } from "../components";
import { PAYMENTS_INVALIDATE } from "./shared";

const EMPTY_WALLET = { wallet_type: "", address: "", api_key: "" };

interface CryptoWalletsSectionProps {
  wallets: PanelWalletRow[];
  availableTypes: string[];
}

export default function CryptoWalletsSection({ wallets, availableTypes }: CryptoWalletsSectionProps) {
  const { t } = useTranslation();
  const createWallet = usePanelAction(panelPaymentsApi.createWallet, { invalidate: PAYMENTS_INVALIDATE });
  const deleteWallet = usePanelAction(panelPaymentsApi.deleteWallet, { invalidate: PAYMENTS_INVALIDATE });
  const [wallet, setWallet] = useState(EMPTY_WALLET);

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

  return (
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
                  onSuccess: () => setWallet(EMPTY_WALLET),
                })
              }
            >
              {t("panel.common.addWallet")}
            </Button>
          </div>
        </div>
      )}
    </SectionCard>
  );
}
