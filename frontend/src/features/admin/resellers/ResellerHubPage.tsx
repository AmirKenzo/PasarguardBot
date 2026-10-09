import { useSearchParams } from "react-router-dom";
import { LayoutDashboard, Receipt, Settings, Tags, Users } from "lucide-react";
import { useTranslation } from "react-i18next";
import { PageHeader } from "../../../components/layout/PageHeader";
import { Tabs } from "../../../components/ui";
import type { TabItem } from "../../../components/ui";
import AccountsTab from "./AccountsTab";
import BillingTab from "./BillingTab";
import OverviewTab from "./OverviewTab";
import PlansTab from "./PlansTab";
import SettingsTab from "./SettingsTab";

export const RESELLER_TABS = ["overview", "accounts", "plans", "billing", "settings"] as const;
export type ResellerTab = (typeof RESELLER_TABS)[number];

/** Pasarguard-panel reseller management: one page, one tab per area. */
export default function ResellerHubPage() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const fromUrl = searchParams.get("tab");
  const tab: ResellerTab = RESELLER_TABS.includes(fromUrl as ResellerTab) ? (fromUrl as ResellerTab) : "overview";

  /** Switch tab, optionally carrying filters (e.g. open one account's ledger). */
  const go = (value: string, extra: Record<string, string> = {}) =>
    setSearchParams(() => new URLSearchParams({ tab: value, ...extra }));

  const items: TabItem[] = [
    { value: "overview", label: t("panel.resellerHub.tabs.overview"), icon: LayoutDashboard },
    { value: "accounts", label: t("panel.resellerHub.tabs.accounts"), icon: Users },
    { value: "plans", label: t("panel.resellerHub.tabs.plans"), icon: Tags },
    { value: "billing", label: t("panel.resellerHub.tabs.billing"), icon: Receipt },
    { value: "settings", label: t("panel.resellerHub.tabs.settings"), icon: Settings },
  ];

  return (
    <>
      <PageHeader title={t("panel.resellerHub.title")} subtitle={t("panel.resellerHub.subtitle")} />
      <div className="mb-4">
        <Tabs items={items} value={tab} onChange={(value) => go(value)} />
      </div>
      {tab === "overview" && <OverviewTab onNavigate={go} />}
      {tab === "accounts" && <AccountsTab onNavigate={go} />}
      {tab === "plans" && <PlansTab />}
      {tab === "billing" && <BillingTab />}
      {tab === "settings" && <SettingsTab />}
    </>
  );
}
