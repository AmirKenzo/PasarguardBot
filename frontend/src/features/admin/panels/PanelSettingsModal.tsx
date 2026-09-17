import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import {
  AlertTriangle,
  Building2,
  Check,
  Gift,
  LayoutGrid,
  Palette,
  RefreshCw,
  Sparkles,
  Users,
  X as XIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import { Button, Input } from "../../../components/ui";
import { SegmentedControl } from "../../../components/ui/Select";
import { FormModal, Toggle } from "../components";
import { panelPanelsApi } from "../../../api/panel";
import type {
  PanelButtonSettings,
  PanelButtonStyleResponse,
  PanelResellerButtonSettings,
  PanelDetailSettingsResponse,
  PanelDetailSettingsSaveRequest,
} from "../../../types/panel";
import { usePanelAction, usePanelQuery } from "../../../queries/usePanelApi";

type TabKey = "style" | "buttons" | "subscription" | "trial" | "renewal" | "features" | "reseller";

const STYLE_COLORS: Record<string, { bg: string; fg: string; border: string }> = {
  primary: { bg: "rgba(59,130,246,0.16)", fg: "#93C5FD", border: "rgba(59,130,246,0.4)" },
  success: { bg: "rgba(34,197,94,0.16)", fg: "#86EFAC", border: "rgba(34,197,94,0.4)" },
  danger: { bg: "rgba(239,68,68,0.16)", fg: "#FCA5A5", border: "rgba(239,68,68,0.4)" },
  "": { bg: "rgba(255,255,255,0.05)", fg: "#C7CCDB", border: "rgba(255,255,255,0.12)" },
};

function buttonDefs(t: TFunction): { key: keyof PanelButtonSettings; label: string; desc: string }[] {
  return [
    { key: "time", label: t("panel.panels.btn.time"), desc: t("panel.panels.btnDesc.time") },
    { key: "volume", label: t("panel.panels.btn.volume"), desc: t("panel.panels.btnDesc.volume") },
    { key: "renew", label: t("panel.panels.btn.renew"), desc: t("panel.panels.btnDesc.renew") },
    { key: "change_subscription", label: t("panel.panels.btn.changeSub"), desc: t("panel.panels.btnDesc.changeSub") },
    { key: "other_links", label: t("panel.panels.btn.otherLinks"), desc: t("panel.panels.btnDesc.otherLinks") },
    { key: "change_link", label: t("panel.panels.btn.changeLink"), desc: t("panel.panels.btnDesc.changeLink") },
    { key: "copy_link", label: t("panel.panels.btn.copyLink"), desc: t("panel.panels.btnDesc.copyLink") },
    { key: "qr", label: t("panel.panels.btn.qr"), desc: t("panel.panels.btnDesc.qr") },
    { key: "transfer", label: t("panel.panels.btn.transfer"), desc: t("panel.panels.btnDesc.transfer") },
    { key: "clients", label: t("panel.panels.btn.clients"), desc: t("panel.panels.btnDesc.clients") },
    { key: "usage_chart", label: t("panel.panels.btn.usageChart"), desc: t("panel.panels.btnDesc.usageChart") },
    { key: "info", label: t("panel.panels.btn.info"), desc: t("panel.panels.btnDesc.info") },
    { key: "delete_service", label: t("panel.panels.btn.deleteService"), desc: t("panel.panels.btnDesc.deleteService") },
  ];
}

function resellerButtonDefs(t: TFunction): { key: keyof PanelResellerButtonSettings; label: string; desc: string }[] {
  return [
    { key: "credentials", label: t("panel.panels.rsBtn.credentials"), desc: t("panel.panels.rsBtnDesc.credentials") },
    { key: "change_password", label: t("panel.panels.rsBtn.changePassword"), desc: t("panel.panels.rsBtnDesc.changePassword") },
    { key: "toggle_status", label: t("panel.panels.rsBtn.toggleStatus"), desc: t("panel.panels.rsBtnDesc.toggleStatus") },
    { key: "usage_report", label: t("panel.panels.rsBtn.usageReport"), desc: t("panel.panels.rsBtnDesc.usageReport") },
    { key: "usage_cap", label: t("panel.panels.rsBtn.usageCap"), desc: t("panel.panels.rsBtnDesc.usageCap") },
    { key: "buy_user_capacity", label: t("panel.panels.rsBtn.buyCapacity"), desc: t("panel.panels.rsBtnDesc.buyCapacity") },
    { key: "delete", label: t("panel.panels.rsBtn.delete"), desc: t("panel.panels.rsBtnDesc.delete") },
  ];
}

function FieldLabel({ children }: { children: ReactNode }) {
  return <span className="mb-1.5 block text-sm text-muted">{children}</span>;
}

function Hint({ children }: { children: ReactNode }) {
  return <p className="mt-1.5 text-xs leading-relaxed text-muted">{children}</p>;
}

export interface PanelSettingsModalProps {
  code: number | null;
  name?: string;
  onClose: () => void;
}

export function PanelSettingsModal({ code, name, onClose }: PanelSettingsModalProps) {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<TabKey>("style");
  const [draft, setDraft] = useState<PanelDetailSettingsResponse | null>(null);
  const [styleDraft, setStyleDraft] = useState<PanelButtonStyleResponse | null>(null);
  const [originalIconId, setOriginalIconId] = useState<string | null | undefined>(null);
  const [newPrefixDraft, setNewPrefixDraft] = useState("");

  const settingsQuery = usePanelQuery(
    ["panel-settings", code],
    (auth) => panelPanelsApi.getPanelSettings({ code: code as number, ...auth }),
    { enabled: code !== null }
  );
  const styleQuery = usePanelQuery(
    ["panel-button-style", code],
    (auth) => panelPanelsApi.getPanelButtonStyle({ code: code as number, ...auth }),
    { enabled: code !== null }
  );
  const groupsQuery = usePanelQuery(
    ["panel-groups", code],
    (auth) => panelPanelsApi.getPanelGroups({ code: code as number, ...auth }),
    { enabled: code !== null }
  );

  useEffect(() => {
    if (settingsQuery.data) setDraft(settingsQuery.data);
  }, [settingsQuery.data]);
  useEffect(() => {
    if (styleQuery.data) {
      setStyleDraft(styleQuery.data);
      setOriginalIconId(styleQuery.data.icon_id ?? null);
    }
  }, [styleQuery.data]);
  useEffect(() => {
    if (code === null) {
      setActiveTab("style");
      setDraft(null);
      setStyleDraft(null);
      setNewPrefixDraft("");
    }
  }, [code]);

  const saveSettings = usePanelAction(panelPanelsApi.savePanelSettings, {
    invalidate: [["panels"], ["panel-settings", code]],
  });
  const saveStyle = usePanelAction(panelPanelsApi.savePanelButtonStyle, {
    invalidate: [["panel-button-style", code]],
  });

  const handleSave = () => {
    if (!draft || !code) return;
    const payload: PanelDetailSettingsSaveRequest = {
      code,
      buttons: draft.buttons,
      subscription: draft.subscription,
      trial: draft.trial,
      renewal: draft.renewal,
      sales: draft.sales,
      custom_buy: draft.custom_buy,
      reseller_capacity: draft.reseller_capacity,
      reseller_buttons: draft.reseller_buttons,
    };
    saveSettings.mutate(payload);
    const styleChanged =
      styleDraft &&
      styleQuery.data &&
      (styleDraft.text !== styleQuery.data.text ||
        styleDraft.style !== styleQuery.data.style ||
        (styleDraft.icon_id ?? null) !== (styleQuery.data.icon_id ?? null));
    if (styleDraft && styleChanged) {
      const iconCleared = originalIconId != null && styleDraft.icon_id == null;
      saveStyle.mutate({
        code,
        text: styleDraft.text,
        style: styleDraft.style,
        icon_id: styleDraft.icon_id ?? undefined,
        clear_icon: iconCleared,
      });
    }
    onClose();
  };

  const isLoading = settingsQuery.isLoading || styleQuery.isLoading;

  const TABS: { key: TabKey; label: string; icon: LucideIcon }[] = [
    { key: "style", label: t("panel.panels.tab.style"), icon: Palette },
    { key: "buttons", label: t("panel.panels.tab.buttons"), icon: LayoutGrid },
    { key: "subscription", label: t("panel.panels.tab.subscription"), icon: Users },
    { key: "trial", label: t("panel.panels.tab.trial"), icon: Gift },
    { key: "renewal", label: t("panel.panels.tab.renewal"), icon: RefreshCw },
    { key: "features", label: t("panel.panels.tab.features"), icon: Sparkles },
    { key: "reseller", label: t("panel.panels.tab.reseller"), icon: Building2 },
  ];

  return (
    <FormModal
      open={code !== null}
      onClose={onClose}
      title={name ? t("panel.panels.settingsTitle", { name }) : t("panel.panels.fullSettings")}
      size="xl"
    >
      {isLoading || !draft || !styleDraft ? (
        <div className="h-72 animate-pulse rounded-md bg-surface-2" />
      ) : (
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap gap-1.5 rounded-md bg-surface-2 p-1.5">
            {TABS.map((tab) => {
              const Icon = tab.icon;
              const active = tab.key === activeTab;
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                    active ? "bg-primary text-primary-text shadow-sm" : "text-muted hover:text-text"
                  }`}
                >
                  <Icon size={13} />
                  {tab.label}
                </button>
              );
            })}
          </div>

          <div className="max-h-[58vh] overflow-y-auto pe-1">
            {activeTab === "style" && (
              <div className="space-y-4">
                <p className="text-xs leading-relaxed text-muted">{t("panel.panels.styleTabHint")}</p>
                <div className="flex flex-col items-center gap-2 rounded-md border border-dashed border-border p-5">
                  <span className="text-xs text-muted">{t("panel.panels.stylePreview")}</span>
                  <span
                    className="inline-flex items-center gap-1.5 rounded-md px-4 py-2 text-sm font-semibold"
                    style={{
                      background: STYLE_COLORS[styleDraft.style]?.bg,
                      color: STYLE_COLORS[styleDraft.style]?.fg,
                      border: `1px solid ${STYLE_COLORS[styleDraft.style]?.border}`,
                    }}
                  >
                    {styleDraft.icon_id ? <span>✨</span> : null}
                    {styleDraft.text || name}
                  </span>
                </div>
                <div>
                  <Input
                    label={t("panel.panels.buttonText")}
                    value={styleDraft.text}
                    onChange={(e) => setStyleDraft({ ...styleDraft, text: e.target.value })}
                  />
                  <Hint>{t("panel.panels.buttonTextHint")}</Hint>
                </div>
                <div>
                  <FieldLabel>{t("panel.panels.buttonColor")}</FieldLabel>
                  <div className="flex flex-wrap gap-2">
                    {(["primary", "success", "danger", ""] as const).map((value) => (
                      <button
                        key={value || "none"}
                        onClick={() => setStyleDraft({ ...styleDraft, style: value })}
                        className={`flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors ${
                          styleDraft.style === value
                            ? "border-primary/40 bg-primary/12 text-primary"
                            : "border-border text-muted hover:text-text"
                        }`}
                      >
                        <span
                          className="h-2 w-2 rounded-full"
                          style={{
                            background: value ? STYLE_COLORS[value]?.fg : "transparent",
                            border: value ? "none" : "1.5px solid currentColor",
                          }}
                        />
                        {value === "primary" && t("panel.panels.colorBlue")}
                        {value === "success" && t("panel.panels.colorGreen")}
                        {value === "danger" && t("panel.panels.colorRed")}
                        {value === "" && t("panel.panels.colorNone")}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <Input
                    label={t("panel.panels.premiumIcon")}
                    ltr
                    inputMode="numeric"
                    value={styleDraft.icon_id ?? ""}
                    onChange={(e) => {
                      const digits = e.target.value.replace(/\D/g, "");
                      setStyleDraft({ ...styleDraft, icon_id: digits || null });
                    }}
                  />
                  <Hint>{t("panel.panels.premiumIconHint")}</Hint>
                  <div className="mt-2 flex gap-2">
                    <button
                      className="rounded-md border border-border px-3 py-1.5 text-xs text-muted hover:bg-surface-2"
                      onClick={() => setStyleDraft({ ...styleDraft, icon_id: null })}
                    >
                      {t("panel.panels.clearIcon")}
                    </button>
                    <button
                      className="rounded-md border border-border px-3 py-1.5 text-xs text-muted hover:bg-surface-2"
                      onClick={() => setStyleDraft({ text: "", style: "", icon_id: null, ok: true })}
                    >
                      {t("panel.panels.resetStyle")}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {activeTab === "buttons" && (
              <div className="space-y-1">
                <p className="mb-2 text-xs leading-relaxed text-muted">{t("panel.panels.buttonsTabHint")}</p>
                {buttonDefs(t).map((def) => (
                  <div key={def.key} className="border-b border-border/50 py-2 last:border-0">
                    <Toggle
                      checked={draft.buttons[def.key]}
                      onChange={(checked) => setDraft({ ...draft, buttons: { ...draft.buttons, [def.key]: checked } })}
                      label={def.label}
                      hint={def.desc}
                    />
                  </div>
                ))}
                <div className="border-t border-border/50 py-2">
                  <Toggle
                    checked={draft.renewal.auto_renew_enabled}
                    onChange={(checked) =>
                      setDraft({ ...draft, renewal: { ...draft.renewal, auto_renew_enabled: checked } })
                    }
                    label={t("panel.panels.btn.autoRenew")}
                    hint={t("panel.panels.btnDesc.autoRenew")}
                  />
                </div>
              </div>
            )}

            {activeTab === "subscription" && (
              <div className="space-y-4">
                <div>
                  <FieldLabel>{t("panel.panels.defaultGroups")}</FieldLabel>
                  <div className="flex flex-wrap gap-1.5">
                    {(groupsQuery.data?.groups || []).map((group) => {
                      const selected = draft.subscription.default_group_ids.includes(group.id);
                      return (
                        <button
                          key={group.id}
                          onClick={() => {
                            const ids = selected
                              ? draft.subscription.default_group_ids.filter((id) => id !== group.id)
                              : [...draft.subscription.default_group_ids, group.id];
                            setDraft({ ...draft, subscription: { ...draft.subscription, default_group_ids: ids } });
                          }}
                          className={`rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
                            selected ? "border-primary/40 bg-primary/12 text-primary" : "border-border text-muted"
                          }`}
                        >
                          {group.name} <span className="opacity-60">#{group.id}</span>
                        </button>
                      );
                    })}
                    {groupsQuery.isLoading && <span className="text-xs text-muted">{t("common.loading")}</span>}
                  </div>
                  <Hint>{t("panel.panels.defaultGroupsHint")}</Hint>
                </div>

                <Input
                  label={t("panel.panels.userLimit")}
                  inputMode="numeric"
                  value={draft.subscription.user_limit ?? ""}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      subscription: { ...draft.subscription, user_limit: e.target.value ? Number(e.target.value) : null },
                    })
                  }
                />

                <div>
                  <FieldLabel>{t("panel.panels.displayMode")}</FieldLabel>
                  <SegmentedControl
                    options={[
                      { value: "classic", label: t("panel.panels.displayClassic") },
                      { value: "duration_first", label: t("panel.panels.displayDuration") },
                    ]}
                    value={draft.subscription.display_mode}
                    onChange={(display_mode) => setDraft({ ...draft, subscription: { ...draft.subscription, display_mode } })}
                  />
                </div>

                <div>
                  <FieldLabel>{t("panel.panels.linkMode")}</FieldLabel>
                  <SegmentedControl
                    options={[
                      { value: "both", label: t("panel.panels.linkBoth") },
                      { value: "main", label: t("panel.panels.linkMain") },
                      { value: "tunnel", label: t("panel.panels.linkTunnel") },
                    ]}
                    value={draft.subscription.link_mode}
                    onChange={(link_mode) => setDraft({ ...draft, subscription: { ...draft.subscription, link_mode } })}
                  />
                </div>

                <div>
                  <Input
                    label={t("panel.panels.singleIndexes")}
                    ltr
                    value={draft.subscription.single_config_link_indexes}
                    onChange={(e) =>
                      setDraft({ ...draft, subscription: { ...draft.subscription, single_config_link_indexes: e.target.value } })
                    }
                  />
                  <Hint>{t("panel.panels.singleIndexesHint")}</Hint>
                </div>

                <Input
                  label={t("panel.panels.adminLoginPath")}
                  ltr
                  value={draft.subscription.admin_login_path}
                  onChange={(e) => setDraft({ ...draft, subscription: { ...draft.subscription, admin_login_path: e.target.value } })}
                />

                <div className="h-px bg-border/60" />

                <div>
                  <FieldLabel>{t("panel.panels.nodePrefixes")}</FieldLabel>
                  <Hint>{t("panel.panels.nodePrefixesHint")}</Hint>
                  <div className="my-2 flex flex-wrap gap-1.5">
                    {draft.subscription.node_prefixes.map((prefix) => (
                      <span
                        key={prefix}
                        className="ltr-field flex items-center gap-1.5 rounded-md border border-primary/30 bg-primary/10 px-2 py-1 text-xs text-primary"
                      >
                        {prefix}
                        <button
                          onClick={() =>
                            setDraft({
                              ...draft,
                              subscription: {
                                ...draft.subscription,
                                node_prefixes: draft.subscription.node_prefixes.filter((p) => p !== prefix),
                              },
                            })
                          }
                        >
                          <XIcon size={11} />
                        </button>
                      </span>
                    ))}
                  </div>
                  <div className="flex gap-2">
                    <Input
                      ltr
                      placeholder={t("panel.panels.nodePrefixPlaceholder")}
                      value={newPrefixDraft}
                      onChange={(e) => setNewPrefixDraft(e.target.value)}
                    />
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => {
                        const value = newPrefixDraft.trim();
                        if (!value || draft.subscription.node_prefixes.includes(value)) return;
                        setDraft({
                          ...draft,
                          subscription: { ...draft.subscription, node_prefixes: [...draft.subscription.node_prefixes, value] },
                        });
                        setNewPrefixDraft("");
                      }}
                    >
                      {t("panel.panels.addPrefix")}
                    </Button>
                  </div>
                </div>

                <Toggle
                  checked={draft.subscription.show_prefixes_in_locations}
                  onChange={(checked) =>
                    setDraft({ ...draft, subscription: { ...draft.subscription, show_prefixes_in_locations: checked } })
                  }
                  label={t("panel.panels.showPrefixes")}
                  hint={t("panel.panels.showPrefixesHint")}
                />
              </div>
            )}

            {activeTab === "trial" && (
              <div className="space-y-4">
                <Toggle
                  checked={draft.trial.enabled}
                  onChange={(checked) => setDraft({ ...draft, trial: { ...draft.trial, enabled: checked } })}
                  label={t("panel.panels.trialEnabled")}
                  hint={t("panel.panels.trialTabHint")}
                />
                <div className="grid gap-3 sm:grid-cols-2">
                  <Input
                    label={t("panel.plans.volumeGb")}
                    inputMode="decimal"
                    value={draft.trial.volume_gb}
                    onChange={(e) => setDraft({ ...draft, trial: { ...draft.trial, volume_gb: Number(e.target.value) } })}
                  />
                  <Input
                    label={t("panel.common.periodDays")}
                    inputMode="numeric"
                    value={draft.trial.duration_days}
                    onChange={(e) => setDraft({ ...draft, trial: { ...draft.trial, duration_days: Number(e.target.value) } })}
                  />
                </div>
              </div>
            )}

            {activeTab === "renewal" && (
              <div className="space-y-4">
                <p className="text-xs leading-relaxed text-muted">{t("panel.panels.renewalTabHint")}</p>
                <Toggle
                  checked={draft.renewal.webhook_notifications_enabled}
                  onChange={(checked) =>
                    setDraft({ ...draft, renewal: { ...draft.renewal, webhook_notifications_enabled: checked } })
                  }
                  label={t("panel.panels.webhookMethod")}
                  hint={t("panel.panels.webhookMethodHint")}
                />
                <div className="flex items-start gap-2 rounded-md border border-danger/30 bg-danger/10 p-3">
                  <AlertTriangle size={15} className="mt-0.5 shrink-0 text-danger" />
                  <p className="text-xs font-semibold leading-relaxed text-danger">{t("panel.panels.webhookWarning")}</p>
                </div>
                <div>
                  <FieldLabel>{t("panel.panels.volumeRenewMode")}</FieldLabel>
                  <SegmentedControl
                    options={[
                      { value: "cumulative", label: t("panel.panels.volumeCumulative") },
                      { value: "reset", label: t("panel.panels.volumeReset") },
                    ]}
                    value={draft.renewal.renew_volume_remaining_mode ? "reset" : "cumulative"}
                    onChange={(value) =>
                      setDraft({ ...draft, renewal: { ...draft.renewal, renew_volume_remaining_mode: value === "reset" } })
                    }
                  />
                  <Hint>{t("panel.panels.volumeRenewModeHint")}</Hint>
                </div>
              </div>
            )}

            {activeTab === "features" && (
              <div className="space-y-4">
                <Toggle
                  checked={draft.sales.shop_enabled}
                  onChange={(checked) => setDraft({ ...draft, sales: { ...draft.sales, shop_enabled: checked } })}
                  label={t("panel.panels.shopSale")}
                  hint={t("panel.panels.shopSaleHint")}
                />
                <div className="h-px bg-border/60" />
                <Toggle
                  checked={draft.custom_buy.enabled}
                  onChange={(checked) => setDraft({ ...draft, custom_buy: { ...draft.custom_buy, enabled: checked } })}
                  label={t("panel.panels.customBuy")}
                  hint={t("panel.panels.customBuyHint")}
                />
                <div className="grid gap-3 sm:grid-cols-3">
                  <Input
                    label={t("panel.panels.customPriceGb")}
                    inputMode="numeric"
                    value={draft.custom_buy.price_per_gb}
                    onChange={(e) => setDraft({ ...draft, custom_buy: { ...draft.custom_buy, price_per_gb: Number(e.target.value) } })}
                  />
                  <Input
                    label={t("panel.panels.customPriceDay")}
                    inputMode="numeric"
                    value={draft.custom_buy.price_per_day}
                    onChange={(e) => setDraft({ ...draft, custom_buy: { ...draft.custom_buy, price_per_day: Number(e.target.value) } })}
                  />
                  <Input
                    label={t("panel.panels.customIpLimit")}
                    inputMode="numeric"
                    value={draft.custom_buy.ip_limit}
                    onChange={(e) => setDraft({ ...draft, custom_buy: { ...draft.custom_buy, ip_limit: Number(e.target.value) } })}
                  />
                  <Input
                    label={t("panel.panels.customMinGb")}
                    inputMode="decimal"
                    value={draft.custom_buy.min_gb}
                    onChange={(e) => setDraft({ ...draft, custom_buy: { ...draft.custom_buy, min_gb: Number(e.target.value) } })}
                  />
                  <Input
                    label={t("panel.panels.customMaxGb")}
                    inputMode="decimal"
                    value={draft.custom_buy.max_gb}
                    onChange={(e) => setDraft({ ...draft, custom_buy: { ...draft.custom_buy, max_gb: Number(e.target.value) } })}
                  />
                  <Input
                    label={t("panel.panels.customMinDays")}
                    inputMode="numeric"
                    value={draft.custom_buy.min_days}
                    onChange={(e) => setDraft({ ...draft, custom_buy: { ...draft.custom_buy, min_days: Number(e.target.value) } })}
                  />
                </div>
              </div>
            )}

            {activeTab === "reseller" && (
              <div className="space-y-4">
                <p className="text-xs leading-relaxed text-muted">{t("panel.panels.resellerTabHint")}</p>
                <Toggle
                  checked={draft.sales.reseller_enabled}
                  onChange={(checked) => setDraft({ ...draft, sales: { ...draft.sales, reseller_enabled: checked } })}
                  label={t("panel.panels.resellerSale")}
                  hint={t("panel.panels.resellerSaleHint")}
                />
                <div className="h-px bg-border/60" />
                <Toggle
                  checked={draft.reseller_capacity.enabled}
                  onChange={(checked) => setDraft({ ...draft, reseller_capacity: { ...draft.reseller_capacity, enabled: checked } })}
                  label={t("panel.panels.resellerCapacity")}
                  hint={t("panel.panels.resellerCapacityHint")}
                />
                <Input
                  label={t("panel.panels.resellerCapacityPrice")}
                  inputMode="numeric"
                  value={draft.reseller_capacity.price_per_user}
                  onChange={(e) =>
                    setDraft({ ...draft, reseller_capacity: { ...draft.reseller_capacity, price_per_user: Number(e.target.value) } })
                  }
                />
                <div className="h-px bg-border/60" />
                <p className="text-xs font-bold text-primary">{t("panel.panels.resellerButtonsTitle")}</p>
                <p className="text-xs text-muted">{t("panel.panels.resellerButtonsHint")}</p>
                {resellerButtonDefs(t).map((def) => (
                  <div key={def.key} className="border-b border-border/50 py-2 last:border-0">
                    <Toggle
                      checked={draft.reseller_buttons[def.key]}
                      onChange={(checked) =>
                        setDraft({ ...draft, reseller_buttons: { ...draft.reseller_buttons, [def.key]: checked } })
                      }
                      label={def.label}
                      hint={def.desc}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="flex justify-end gap-2 border-t border-border pt-3">
            <Button size="sm" variant="ghost" onClick={onClose}>
              {t("panel.common.dismiss")}
            </Button>
            <Button size="sm" loading={saveSettings.isPending || saveStyle.isPending} onClick={handleSave}>
              <Check size={16} />
              {t("common.save")}
            </Button>
          </div>
        </div>
      )}
    </FormModal>
  );
}
