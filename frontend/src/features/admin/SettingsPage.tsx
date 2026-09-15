import { useEffect, useState } from "react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button, ErrorState, Input, SegmentedControl, Skeleton, Tabs } from "../../components/ui";
import { panelSettingsApi } from "../../api/panel";
import type { PanelSettingValue } from "../../types/panel";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { IconPickerField, SectionCard, Toggle } from "./components";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

// These pick from a fixed set of emoji, so they get an icon-grid picker instead
// of a text pill row or a dropdown — see IconPickerField.
const ICON_PICKER_FIELDS = new Set(["start_reaction_emoji", "start_effect_id"]);

const sectionTitles = (t: TFunction): Record<string, string> => ({
  core_settings: t("panel.settings.core"),
  payment_settings: t("panel.settings.paymentsAndWallet"),
  purchase_settings: t("panel.settings.buyAndRenew"),
  service_tools_settings: t("panel.settings.serviceTools"),
  reseller_settings: t("panel.common.reseller"),
});

const labels = (t: TFunction): Record<string, string> => ({
  bot_mode: t("panel.settings.botEnabled"),
  sale_mode: t("panel.settings.salesEnabled"),
  single_panel_buy_mode: t("panel.settings.singlePanelPurchase"),
  channel_lock: t("panel.settings.channelLock"),
  miniapp_only_mode: t("panel.settings.miniappOnly"),
  glass_keyboard_mode: t("panel.settings.glassKeyboard"),
  start_reaction_emoji: t("panel.settings.startReactionEmoji"),
  start_effect_id: t("panel.settings.startEffectId"),
  backup_interval_hours: t("panel.settings.backupInterval"),
  profile_mode: t("panel.settings.showProfile"),
  help_mode: t("panel.settings.showHelp"),
  support_mode: t("panel.settings.showSupport"),
  advanced_settings_mode: t("panel.settings.advancedUser"),
  premium_emoji_status: t("panel.common.premiumEmoji"),
  pay_mode: t("panel.settings.paymentEnabled"),
  pay_phone_verify: t("panel.settings.phoneRequiredForPayment"),
  arz_mode: t("panel.common.cryptoPayment"),
  manual_card_visibility: t("panel.settings.showManualCard"),
  manual_auto_confirm: t("panel.common.autoApproveCardTransfer"),
  manual_card_random_mode: t("panel.settings.randomCard"),
  manual_deposit_min: t("panel.settings.manualMin"),
  manual_deposit_max: t("panel.settings.manualMax"),
  crypto_deposit_min: t("panel.settings.cryptoMin"),
  crypto_deposit_max: t("panel.settings.cryptoMax"),
  manual_bonus_enabled: t("panel.settings.manualTopUpBonus"),
  manual_bonus_percent: t("panel.settings.manualBonusPercent"),
  crypto_bonus_enabled: t("panel.settings.cryptoTopUpBonus"),
  crypto_bonus_percent: t("panel.settings.cryptoBonusPercent"),
  arz_usd: t("panel.settings.usdPrice"),
  arz_trx: t("panel.settings.tronPrice"),
  arz_ton: t("panel.settings.tonPrice"),
  extension_mode: t("panel.settings.renewService"),
  upg_mode: t("panel.settings.serviceUpgrade"),
  tamdid_mode: t("panel.settings.extraVolume"),
  test_mode: t("panel.settings.trialService"),
  test_panel_id: t("panel.settings.trialPanelCode"),
  test_phone_verify: t("panel.settings.phoneRequiredForTrial"),
  direct_pay_purchase_mode: t("panel.settings.directBuy"),
  direct_pay_renew_mode: t("panel.settings.directRenew"),
  qr_mode: t("panel.settings.showQr"),
  sub_mode: t("panel.settings.subLink"),
  other_links_mode: t("panel.settings.otherLinks"),
  client_list_mode: t("panel.settings.clientList"),
  usage_chart_mode: t("panel.settings.usageChart"),
  change_link_mode: t("panel.settings.changeLink"),
  copy_link_mode: t("panel.settings.copyLink"),
  transfer_config_mode: t("panel.settings.transferConfig"),
  info_mode: t("panel.settings.serviceInfo"),
  del_service_mode: t("panel.common.deleteService"),
  reseller_sale_mode: t("panel.settings.resellerSales"),
  reseller_min_wallet_balance: t("panel.settings.resellerMinBalance"),
});

export default function AdminSettingsPage() {
  const { t } = useTranslation();
  const [values, setValues] = useState<Record<string, PanelSettingValue> | null>(null);
  const [activeSection, setActiveSection] = useState<string | null>(null);

  const query = usePanelQuery(["settings"], (auth) => panelSettingsApi.getSettings(auth));
  const save = usePanelAction(panelSettingsApi.saveSettings, { invalidate: [["settings"], ["keyboard"]] });

  useEffect(() => {
    if (!query.data || values !== null) return;
    const next: Record<string, PanelSettingValue> = {};
    for (const section of query.data.sections) {
      for (const field of section.fields) next[field.key] = field.value;
    }
    setValues(next);
    setActiveSection(query.data.sections[0]?.key ?? null);
  }, [query.data, values]);

  if (query.isError) {
    return <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />;
  }
  if (query.isLoading || !query.data || !values || !activeSection) {
    return <Skeleton className="h-64 w-full" />;
  }

  const section = query.data.sections.find((item) => item.key === activeSection) || query.data.sections[0];
  if (!section) {
    return <Skeleton className="h-64 w-full" />;
  }

  const saveSection = () => {
    const sectionValues: Record<string, PanelSettingValue> = {};
    for (const field of section.fields) {
      if (!field.read_only) sectionValues[field.key] = values[field.key] ?? null;
    }
    save.mutate({ values: sectionValues });
  };

  const toggles = section.fields.filter((field) => field.type === "bool");
  const selects = section.fields.filter((field) => field.type === "select");
  const numbers = section.fields.filter((field) => field.type === "number" && !field.read_only);
  const texts = section.fields.filter((field) => field.type === "text");
  const readOnlyFields = section.fields.filter((field) => field.read_only);

  return (
    <>
      <PageHeader
        title={t("panel.common.botSettings")}
        subtitle={query.data.initialized ? undefined : t("panel.settings.noRowYet")}
      />

      <div className="mb-4">
        <Tabs
          items={query.data.sections.map((item) => ({
            value: item.key,
            label: sectionTitles(t)[item.key] || item.key,
          }))}
          value={section.key}
          onChange={(value) => setActiveSection(value)}
        />
      </div>

      <SectionCard
        title={sectionTitles(t)[section.key] || section.key}
        actions={
          <Button size="sm" loading={save.isPending} onClick={saveSection}>
            {t("panel.settings.saveSection")}
          </Button>
        }
      >
        {toggles.length > 0 && (
          <div className="grid gap-1 sm:grid-cols-2">
            {toggles.map((field) => (
              <Toggle
                key={field.key}
                checked={Boolean(values[field.key])}
                onChange={(checked) => setValues({ ...values, [field.key]: checked })}
                label={labels(t)[field.key] || field.key}
              />
            ))}
          </div>
        )}

        {selects.length > 0 && (
          <div className={`grid gap-3 sm:grid-cols-2 ${toggles.length ? "mt-4 border-t border-border pt-4" : ""}`}>
            {selects.map((field) => {
              const options = field.options || [];
              const current = String(values[field.key] ?? options[0]?.value ?? "");
              return (
                <div key={field.key}>
                  {ICON_PICKER_FIELDS.has(field.key) ? (
                    <IconPickerField
                      label={labels(t)[field.key] || field.key}
                      value={current}
                      onChange={(value) => setValues({ ...values, [field.key]: value })}
                      options={options}
                    />
                  ) : (
                    <>
                      <span className="mb-1.5 block text-sm text-muted">{labels(t)[field.key] || field.key}</span>
                      <SegmentedControl
                        value={current}
                        onChange={(value) => setValues({ ...values, [field.key]: value })}
                        options={options}
                      />
                    </>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {numbers.length > 0 && (
          <div
            className={`grid gap-3 sm:grid-cols-2 ${
              toggles.length || selects.length ? "mt-4 border-t border-border pt-4" : ""
            }`}
          >
            {numbers.map((field) => (
              <Input
                key={field.key}
                label={labels(t)[field.key] || field.key}
                inputMode="numeric"
                value={values[field.key] === null || values[field.key] === undefined ? "" : String(values[field.key])}
                onChange={(event) =>
                  setValues({
                    ...values,
                    [field.key]: event.target.value.trim() === "" ? null : Number(event.target.value),
                  })
                }
              />
            ))}
          </div>
        )}

        {texts.length > 0 && (
          <div
            className={`grid gap-3 sm:grid-cols-2 ${
              toggles.length || selects.length || numbers.length ? "mt-4 border-t border-border pt-4" : ""
            }`}
          >
            {texts.map((field) => (
              <Input
                key={field.key}
                label={labels(t)[field.key] || field.key}
                value={values[field.key] === null || values[field.key] === undefined ? "" : String(values[field.key])}
                onChange={(event) => setValues({ ...values, [field.key]: event.target.value })}
              />
            ))}
          </div>
        )}

        {readOnlyFields.length > 0 && (
          <div className="mt-4 border-t border-border pt-4">
            <p className="mb-2 text-xs text-muted">{t("panel.settings.readOnlyHint")}</p>
            <div className="grid gap-3 sm:grid-cols-2">
              {readOnlyFields.map((field) => (
                <Input
                  key={field.key}
                  label={labels(t)[field.key] || field.key}
                  value={values[field.key] === null || values[field.key] === undefined ? "" : String(values[field.key])}
                  disabled
                  readOnly
                  className="cursor-not-allowed opacity-60"
                />
              ))}
            </div>
          </div>
        )}
      </SectionCard>
    </>
  );
}
