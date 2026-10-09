import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, Save, Search, SearchX } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Badge, Button, EmptyState, ErrorState, Input, Skeleton } from "../../../components/ui";
import { panelResellersApi } from "../../../api/panel";
import { formatNumber } from "../../../lib/format";
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

/** Panels shown before "show more"; long lists stay light. */
const PAGE_SIZE = 30;

/** Persian/Arabic digits to ASCII so a typed panel code matches either way. */
function normalizeSearch(value: string): string {
  return value
    .replace(/[\u0660-\u0669]/g, (digit) => String(digit.charCodeAt(0) - 0x0660))
    .replace(/[\u06f0-\u06f9]/g, (digit) => String(digit.charCodeAt(0) - 0x06f0))
    .trim()
    .toLowerCase();
}

/** A bare switch for dense rows (Toggle carries its own label). */
function Switch({ checked, onChange, label }: { checked: boolean; onChange: (checked: boolean) => void; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      title={label}
      onClick={() => onChange(!checked)}
      className={`h-6 w-11 shrink-0 rounded-full border transition-colors ${
        checked ? "border-primary bg-primary" : "border-border bg-surface-2"
      }`}
    >
      <span
        className={`block h-5 w-5 rounded-full bg-white shadow transition-transform ${
          checked ? "-translate-x-[22px]" : "-translate-x-0.5"
        }`}
      />
    </button>
  );
}

const allButtons = (value: boolean): Partial<PanelResellerButtons> =>
  Object.fromEntries(BUTTON_KEYS.map((key) => [key, value]));

export default function SettingsTab() {
  const { t } = useTranslation();
  const query = usePanelQuery(["reseller-settings"], (auth) => panelResellersApi.getSettings(auth));
  const save = usePanelAction(panelResellersApi.saveSettings, {
    invalidate: [["reseller-settings"], ["reseller-overview"]],
  });

  const [settings, setSettings] = useState<PanelResellerGlobalSettings | null>(null);
  const [panels, setPanels] = useState<PanelResellerPanelSettings[]>([]);
  const [search, setSearch] = useState("");
  const [limit, setLimit] = useState(PAGE_SIZE);
  const [openCode, setOpenCode] = useState<number | null>(null);

  useEffect(() => {
    if (!query.data) return;
    setSettings(query.data.settings);
    setPanels(query.data.panels);
  }, [query.data]);

  const needle = normalizeSearch(search);
  const matches = useMemo(
    () =>
      needle
        ? panels.filter(
            (panel) => normalizeSearch(panel.name || "").includes(needle) || String(panel.code).includes(needle)
          )
        : panels,
    [panels, needle]
  );

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
        <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
          <div className="min-w-0">
            <h3 className="mb-1 text-sm font-semibold text-text">
              {t("panel.resellerHub.settings.panels")}
              <span className="ms-1.5 text-xs font-normal text-muted">{formatNumber(panels.length)}</span>
            </h3>
            <p className="text-xs text-muted">{t("panel.resellerHub.settings.panelsHint")}</p>
          </div>
          {panels.length > 1 && (
            <div className="w-full sm:w-72">
              <Input
                dense
                type="search"
                value={search}
                placeholder={t("panel.resellerHub.settings.searchPanels")}
                aria-label={t("panel.resellerHub.settings.searchPanels")}
                suffix={<Search size={15} />}
                onChange={(event) => {
                  setSearch(event.target.value);
                  setLimit(PAGE_SIZE);
                }}
              />
            </div>
          )}
        </div>

        {matches.length === 0 ? (
          <div className="rounded-xl border border-border bg-surface p-4">
            <EmptyState icon={SearchX} title={t("panel.resellerHub.settings.noPanelMatch")} />
          </div>
        ) : (
          <ul className="divide-y divide-border/60 overflow-hidden rounded-xl border border-border bg-surface">
            {matches.slice(0, limit).map((panel) => {
              const open = openCode === panel.code;
              const onCount = BUTTON_KEYS.filter((key) => panel.buttons[key]).length;
              const saved = original?.panels.find((item) => item.code === panel.code);
              const edited = JSON.stringify(panel) !== JSON.stringify(saved);
              return (
                <li key={panel.code} className={open ? "bg-surface-2/40" : undefined}>
                  <div className="flex items-center gap-3 px-3 py-2.5 sm:px-4">
                    <button
                      type="button"
                      aria-expanded={open}
                      onClick={() => setOpenCode(open ? null : panel.code)}
                      className="flex min-w-0 flex-1 items-center gap-2.5 text-start"
                    >
                      <ChevronDown
                        size={16}
                        className={`shrink-0 text-muted transition-transform ${open ? "rotate-180" : ""}`}
                      />
                      <span className="min-w-0 flex-1">
                        <span className="flex min-w-0 items-center gap-1.5">
                          <span className="truncate text-sm font-medium text-text">{panel.name || `#${panel.code}`}</span>
                          <span className="ltr-field shrink-0 text-[11px] text-muted">#{panel.code}</span>
                          {edited && (
                            <span
                              className="h-1.5 w-1.5 shrink-0 rounded-full bg-warning"
                              title={t("panel.resellerHub.settings.edited")}
                            />
                          )}
                        </span>
                        <span className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
                          <span>
                            {t("panel.resellerHub.settings.buttonsOn", {
                              on: formatNumber(onCount),
                              total: formatNumber(BUTTON_KEYS.length),
                            })}
                          </span>
                          {!panel.enable && <Badge tone="danger">{t("panel.resellerHub.settings.panelOff")}</Badge>}
                        </span>
                      </span>
                    </button>
                    <span className="hidden text-xs text-muted sm:inline">
                      {t(panel.sale_enabled ? "panel.resellerHub.settings.saleOn" : "panel.resellerHub.settings.saleOff")}
                    </span>
                    <Switch
                      checked={panel.sale_enabled}
                      onChange={(sale_enabled) => patchPanel(panel.code, { sale_enabled })}
                      label={t("panel.resellerHub.settings.panelSale")}
                    />
                  </div>
                  <AnimatePresence initial={false}>
                    {open && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="overflow-hidden"
                      >
                        <div className="space-y-3 border-t border-border/60 px-3 pb-3 pt-2 sm:px-4">
                          <div className="flex items-center justify-between gap-3">
                            <p className="text-xs font-semibold text-muted">{t("panel.resellerHub.settings.buttons")}</p>
                            <div className="flex gap-1">
                              <Button
                                size="sm"
                                variant="ghost"
                                disabled={onCount === BUTTON_KEYS.length}
                                onClick={() => patchPanel(panel.code, { buttons: { ...panel.buttons, ...allButtons(true) } })}
                              >
                                {t("panel.resellerHub.settings.allOn")}
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                disabled={onCount === 0}
                                onClick={() => patchPanel(panel.code, { buttons: { ...panel.buttons, ...allButtons(false) } })}
                              >
                                {t("panel.resellerHub.settings.allOff")}
                              </Button>
                            </div>
                          </div>
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
                          <p className="rounded-lg bg-surface-2/60 px-3 py-2 text-xs leading-6 text-muted">
                            {t("panel.resellerHub.settings.capacityMoved")}
                          </p>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </li>
              );
            })}
          </ul>
        )}

        {matches.length > limit && (
          <div className="mt-3 flex justify-center">
            <Button size="sm" variant="secondary" onClick={() => setLimit((value) => value + PAGE_SIZE)}>
              {t("panel.resellerHub.settings.showMore", {
                count: formatNumber(Math.min(PAGE_SIZE, matches.length - limit)),
              })}
            </Button>
          </div>
        )}
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
