import { useEffect, useState } from "react";
import { Save, Server } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Badge, Button, ErrorState, Input, Skeleton } from "../../../components/ui";
import { panelResellersApi } from "../../../api/panel";
import type {
  PanelResellerButtons,
  PanelResellerGlobalSettings,
  PanelResellerPanelSettings,
} from "../../../types/panel";
import { usePanelAction, usePanelQuery } from "../../../queries/usePanelApi";
import { SectionCard, Toggle } from "../components";

const BUTTON_KEYS: (keyof PanelResellerButtons)[] = [
  "credentials",
  "change_password",
  "toggle_status",
  "usage_report",
  "usage_cap",
  "buy_user_capacity",
  "extra_days",
  "extra_volume",
  "delete",
];

/** Add-on buttons get a hint: they also need a price on the plan to show. */
const BUTTON_HINTS: ReadonlySet<keyof PanelResellerButtons> = new Set(["buy_user_capacity", "extra_days", "extra_volume"]);

export default function SettingsTab() {
  const { t } = useTranslation();
  const query = usePanelQuery(["reseller-settings"], (auth) => panelResellersApi.getSettings(auth));
  const save = usePanelAction(panelResellersApi.saveSettings, {
    invalidate: [["reseller-settings"], ["reseller-overview"]],
  });

  const [settings, setSettings] = useState<PanelResellerGlobalSettings | null>(null);
  const [panels, setPanels] = useState<PanelResellerPanelSettings[]>([]);

  useEffect(() => {
    if (!query.data) return;
    setSettings(query.data.settings);
    setPanels(query.data.panels);
  }, [query.data]);

  if (query.isError) return <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />;
  if (!settings) return <Skeleton className="h-64 w-full" />;

  const original = query.data;
  const settingsDirty = JSON.stringify(settings) !== JSON.stringify(original?.settings);
  const changedPanels = panels.filter(
    (panel) => JSON.stringify(panel) !== JSON.stringify(original?.panels.find((item) => item.code === panel.code))
  );
  const dirty = settingsDirty || changedPanels.length > 0;

  const patchPanel = (code: number, patch: Partial<PanelResellerPanelSettings>) =>
    setPanels((prev) => prev.map((panel) => (panel.code === code ? { ...panel, ...patch } : panel)));

  const numberInput = (key: keyof PanelResellerGlobalSettings, label: string, hint: string) => (
    <div>
      <Input
        label={label}
        inputMode="numeric"
        value={String(settings[key] ?? "")}
        onChange={(event) => setSettings({ ...settings, [key]: Number(event.target.value.replace(/\D/g, "")) || 0 })}
      />
      <p className="mt-1 text-xs text-muted">{hint}</p>
    </div>
  );

  return (
    <div className="space-y-4 pb-20">
      <SectionCard title={t("panel.resellerHub.settings.global")} description={t("panel.resellerHub.settings.globalHint")}>
        <div className="space-y-4">
          <div className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
            <Toggle
              checked={settings.sale_mode}
              onChange={(sale_mode) => setSettings({ ...settings, sale_mode })}
              label={t("panel.resellerHub.settings.saleMode")}
              hint={t("panel.resellerHub.settings.saleModeHint")}
            />
            <Toggle
              checked={settings.usage_debt}
              onChange={(usage_debt) => setSettings({ ...settings, usage_debt })}
              label={t("panel.resellerHub.settings.usageDebt")}
              hint={t("panel.resellerHub.settings.usageDebtHint")}
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            {numberInput("min_wallet_balance", t("panel.resellerHub.settings.minWallet"), t("panel.resellerHub.settings.minWalletHint"))}
            {numberInput("grace_days", t("panel.resellerHub.settings.graceDays"), t("panel.resellerHub.settings.graceDaysHint"))}
            {numberInput(
              "low_balance_hours",
              t("panel.resellerHub.settings.lowBalanceHours"),
              t("panel.resellerHub.settings.lowBalanceHoursHint")
            )}
          </div>
        </div>
      </SectionCard>

      <div>
        <h3 className="mb-1 text-sm font-semibold text-text">{t("panel.resellerHub.settings.panels")}</h3>
        <p className="mb-3 text-xs text-muted">{t("panel.resellerHub.settings.panelsHint")}</p>
        <div className="grid gap-4 lg:grid-cols-2">
          {panels.map((panel) => (
            <SectionCard
              key={panel.code}
              title={panel.name || `#${panel.code}`}
              actions={
                <>
                  <Server size={14} className="text-muted" />
                  {!panel.enable && <Badge tone="danger">{t("panel.resellerHub.settings.panelOff")}</Badge>}
                </>
              }
            >
              <div className="space-y-3">
                <Toggle
                  checked={panel.sale_enabled}
                  onChange={(sale_enabled) => patchPanel(panel.code, { sale_enabled })}
                  label={t("panel.resellerHub.settings.panelSale")}
                />
                <p className="rounded-lg bg-surface-2/60 px-3 py-2 text-xs leading-6 text-muted">
                  {t("panel.resellerHub.settings.capacityMoved")}
                </p>
                <div>
                  <p className="mb-1 text-xs font-semibold text-muted">{t("panel.resellerHub.settings.buttons")}</p>
                  <div className="grid gap-x-4 sm:grid-cols-2">
                    {BUTTON_KEYS.map((key) => (
                      <Toggle
                        key={key}
                        checked={panel.buttons[key]}
                        onChange={(value) => patchPanel(panel.code, { buttons: { ...panel.buttons, [key]: value } })}
                        label={t(`panel.resellerHub.settings.button.${key}`)}
                        hint={BUTTON_HINTS.has(key) ? t(`panel.resellerHub.settings.buttonHint.${key}`) : undefined}
                      />
                    ))}
                  </div>
                </div>
              </div>
            </SectionCard>
          ))}
        </div>
      </div>

      {dirty && (
        <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-surface/95 px-4 py-3 backdrop-blur md:start-60">
          <div className="mx-auto flex max-w-5xl items-center justify-between gap-3">
            <span className="text-sm text-muted">{t("panel.resellerHub.settings.unsaved")}</span>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  setSettings(original!.settings);
                  setPanels(original!.panels);
                }}
              >
                {t("panel.common.dismiss")}
              </Button>
              <Button
                size="sm"
                loading={save.isPending}
                onClick={() =>
                  save.mutate({
                    settings: settingsDirty ? settings : null,
                    panels: changedPanels.length ? changedPanels : null,
                  })
                }
              >
                <Save size={14} />
                {t("common.save")}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
