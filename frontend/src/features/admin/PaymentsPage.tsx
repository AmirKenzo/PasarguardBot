import { useSearchParams } from "react-router-dom";
import { CreditCard, Gem, Landmark, Wallet } from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { ErrorState, Skeleton, Tabs } from "../../components/ui";
import type { TabItem } from "../../components/ui";
import { panelPaymentsApi } from "../../api/panel";
import { usePanelQuery } from "../../queries/usePanelApi";
import { useTranslation } from "react-i18next";
import TonPaysTab from "./TonPaysTab";
import IrGatewaysTab from "./IrGatewaysTab";
import CryptoWalletsSection from "./payments/CryptoWalletsSection";
import ManualCardsSection from "./payments/ManualCardsSection";
import AutoApproveRulesSection from "./payments/AutoApproveRulesSection";

const SECTIONS = ["crypto", "manual", "tonpays", "ir-gateways"] as const;
type Section = (typeof SECTIONS)[number];

export default function AdminPaymentsPage() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const fromUrl = searchParams.get("section");
  const section: Section = SECTIONS.includes(fromUrl as Section) ? (fromUrl as Section) : "crypto";
  const setSection = (value: string) =>
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("section", value);
      return next;
    });
  const query = usePanelQuery(["payments"], (auth) => panelPaymentsApi.getPayments(auth));

  const tabItems: TabItem[] = [
    { value: "crypto", label: t("panel.payments.tabCrypto"), icon: Wallet },
    { value: "manual", label: t("panel.payments.tabManual"), icon: CreditCard },
    { value: "tonpays", label: t("panel.payments.tabTonPays"), icon: Gem },
    { value: "ir-gateways", label: t("panel.payments.tabIrGateways"), icon: Landmark },
  ];
  const header = (
    <>
      <PageHeader title={t("panel.common.paymentGateways")} subtitle={t("panel.payments.subtitle")} />
      <div className="mb-4">
        <Tabs items={tabItems} value={section} onChange={setSection} />
      </div>
    </>
  );

  if (section === "tonpays") {
    return (
      <>
        {header}
        <TonPaysTab />
      </>
    );
  }
  if (section === "ir-gateways") {
    return (
      <>
        {header}
        <IrGatewaysTab />
      </>
    );
  }
  if (query.isLoading) {
    return <Skeleton className="h-64 w-full" />;
  }
  if (query.isError || !query.data) {
    return <ErrorState message={query.error?.message || t("common.error")} onRetry={() => void query.refetch()} />;
  }

  const { wallets, available_wallet_types: availableTypes, cards, rules } = query.data;

  return (
    <>
      {header}

      {section === "crypto" && <CryptoWalletsSection wallets={wallets} availableTypes={availableTypes} />}

      {section === "manual" && (
        <>
          <ManualCardsSection cards={cards} />
          <AutoApproveRulesSection rules={rules} />
        </>
      )}
    </>
  );
}
