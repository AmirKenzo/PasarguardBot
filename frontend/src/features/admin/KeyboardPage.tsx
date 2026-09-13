import { useEffect, useState } from "react";
import { AlertTriangle, ChevronDown, ChevronRight, ChevronLeft, ChevronUp, Eye, EyeOff, Plus } from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge, Button, ErrorState, Input, Skeleton } from "../../components/ui";
import { panelKeyboardApi } from "../../api/panel";
import type { PanelKeyboardButton } from "../../types/panel";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { ConfirmButton, DataTable, SectionCard, SelectField } from "./components";
import type { Column } from "./components";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

const sectionLabels = (t: TFunction): Record<string, string> => ({
  main_menu: t("panel.keyboard.mainMenu"),
  my_services: t("panel.keyboard.myServices"),
  balance: t("panel.common.addBalance"),
  buy: t("panel.keyboard.buyService"),
  other: t("panel.keyboard.other"),
});

// Why the bot will not render a button, whatever the admin's switch says.
const blockedLabels = (t: TFunction): Record<string, string> => ({
  no_shop_panel: t("panel.keyboard.blockedNoShopPanel"),
  reseller_sale_off: t("panel.keyboard.blockedResellerOff"),
  trial_off: t("panel.keyboard.blockedTrialOff"),
  setting_off: t("panel.keyboard.blockedBySetting"),
  uptime_disabled: t("panel.keyboard.blockedUptime"),
});

const styleLabels = (t: TFunction): Record<string, string> => ({
  "": t("panel.common.default"),
  primary: t("panel.common.blue"),
  success: t("panel.common.green"),
  danger: t("panel.common.red"),
  none: t("panel.keyboard.noColour"),
});

const INVALIDATE = [["keyboard"]];

export default function AdminKeyboardPage() {
  const { t } = useTranslation();
  const query = usePanelQuery(["keyboard"], (auth) => panelKeyboardApi.getKeyboard(auth));

  const saveLayout = usePanelAction(panelKeyboardApi.saveLayout, { invalidate: INVALIDATE });
  const resetLayout = usePanelAction(panelKeyboardApi.resetLayout, { invalidate: INVALIDATE });
  const clearIcon = usePanelAction(panelKeyboardApi.clearIcon, { invalidate: INVALIDATE });

  const [layout, setLayout] = useState<string[][]>([]);
  const [hidden, setHidden] = useState<string[]>([]);
  const [openKey, setOpenKey] = useState<string | null>(null);

  useEffect(() => {
    if (!query.data) return;
    setLayout(query.data.layout.map((row) => [...row]));
    setHidden(query.data.buttons.filter((button) => button.hidden).map((button) => button.key));
  }, [query.data]);

  if (query.isError) {
    return <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />;
  }
  if (query.isLoading || !query.data) {
    return <Skeleton className="h-64 w-full" />;
  }

  const buttonsByKey = new Map<string, PanelKeyboardButton>(
    query.data.buttons.map((button) => [button.key, button])
  );
  const labelFor = (key: string) => {
    const button = buttonsByKey.get(key);
    return button?.text || button?.default_text || button?.title || key;
  };

  function move(rowIndex: number, position: number, direction: "up" | "down" | "start" | "end") {
    setLayout((current) => {
      const next = current.map((row) => [...row]);
      const row = next[rowIndex];
      if (!row) return current;
      const [key] = row.splice(position, 1);
      if (key === undefined) return current;

      if (direction === "start" || direction === "end") {
        const target = direction === "start" ? position - 1 : position + 1;
        row.splice(Math.max(0, Math.min(row.length, target)), 0, key);
      } else {
        const targetIndex = direction === "up" ? rowIndex - 1 : rowIndex + 1;
        if (targetIndex < 0) next.unshift([key]);
        else if (targetIndex >= next.length) next.push([key]);
        else next[targetIndex]?.push(key);
      }
      return next.filter((item) => item.length > 0);
    });
  }

  function toggleHidden(key: string) {
    setHidden((current) => (current.includes(key) ? current.filter((item) => item !== key) : [...current, key]));
  }

  const iconRows = query.data.buttons.filter((button) => button.icon);
  const iconColumns: Column<PanelKeyboardButton>[] = [
    { key: "title", header: t("panel.keyboard.button"), cell: (row) => row.title || row.key },
    { key: "key", header: t("panel.keyboard.key"), secondary: true, cell: (row) => <code className="ltr-field text-xs">{row.key}</code> },
    { key: "icon", header: t("panel.keyboard.emojiId"), cell: (row) => <code className="ltr-field text-xs">{row.icon}</code> },
    {
      key: "actions",
      header: "",
      cell: (row) => (
        <ConfirmButton
          size="sm"
          variant="danger"
          message={t("panel.keyboard.iconClearConfirm")}
          onConfirm={() => clearIcon.mutate({ key: row.key })}
        >
          {t("panel.keyboard.clearIcon")}
        </ConfirmButton>
      ),
    },
  ];

  const sections = query.data.sections.filter((section) =>
    query.data?.buttons.some((button) => button.section === section)
  );

  return (
    <>
      <PageHeader title={t("panel.common.keyboardLayout")} subtitle={t("panel.keyboard.subtitle")} />

      <SectionCard
        title={t("panel.keyboard.mainMenuLayout")}
        description={t("panel.keyboard.hiddenNote")}
        actions={
          <>
            <Button size="sm" variant="ghost" onClick={() => setLayout((current) => [...current, []])}>
              <Plus size={15} />
              {t("panel.keyboard.emptyRow")}
            </Button>
            <ConfirmButton
              size="sm"
              variant="ghost"
              message={t("panel.keyboard.resetConfirm")}
              onConfirm={() => resetLayout.mutate({})}
            >
              {t("panel.common.restoreDefaults")}
            </ConfirmButton>
            <Button
              size="sm"
              loading={saveLayout.isPending}
              onClick={() => saveLayout.mutate({ layout, hidden })}
            >
              {t("panel.keyboard.saveLayout")}
            </Button>
          </>
        }
      >
        <div className="space-y-2">
          {layout.map((row, rowIndex) => (
            <div key={rowIndex} className="rounded-md border border-border p-2">
              <p className="mb-2 text-[11px] text-muted">{t("panel.keyboard.row")} {rowIndex + 1}</p>
              {row.length === 0 ? (
                <p className="py-2 text-center text-xs text-muted">
                  {t("panel.keyboard.emptyRowHint")}
                </p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {row.map((key, position) => {
                    const isHidden = hidden.includes(key);
                    const blocked = buttonsByKey.get(key)?.blocked || "";
                    return (
                      <div
                        key={key}
                        title={blocked ? blockedLabels(t)[blocked] || blocked : undefined}
                        className={`flex items-center gap-1 rounded-md border px-2 py-1.5 text-sm ${
                          isHidden ? "border-dashed border-border bg-surface-2 text-muted" : "border-border bg-surface"
                        } ${blocked ? "opacity-70" : ""}`}
                      >
                        <ChipButton label={t("panel.keyboard.moveRight")} onClick={() => move(rowIndex, position, "start")}>
                          <ChevronRight size={14} />
                        </ChipButton>
                        <ChipButton label={t("panel.keyboard.moveLeft")} onClick={() => move(rowIndex, position, "end")}>
                          <ChevronLeft size={14} />
                        </ChipButton>
                        <span className="px-1">{labelFor(key)}</span>
                        {blocked && <AlertTriangle size={13} className="shrink-0 text-warning" />}
                        <ChipButton label={t("panel.keyboard.rowUp")} onClick={() => move(rowIndex, position, "up")}>
                          <ChevronUp size={14} />
                        </ChipButton>
                        <ChipButton label={t("panel.keyboard.rowDown")} onClick={() => move(rowIndex, position, "down")}>
                          <ChevronDown size={14} />
                        </ChipButton>
                        <ChipButton
                          label={isHidden ? t("panel.keyboard.showToUser") : t("panel.keyboard.hideFromUser")}
                          onClick={() => toggleHidden(key)}
                        >
                          {isHidden ? <EyeOff size={14} /> : <Eye size={14} className="text-success" />}
                        </ChipButton>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          ))}
        </div>
        <p className="mt-3 text-xs text-muted">
          {t("panel.keyboard.layoutHintStart")}
          {t("panel.keyboard.layoutHintEnd")}
        </p>
      </SectionCard>

      <SectionCard
        title={t("panel.common.premiumEmoji")}
        description={
          query.data.premium_emoji_enabled
            ? t("panel.keyboard.premiumEmojiOn")
            : t("panel.keyboard.premiumEmojiOff")
        }
      >
        <DataTable
          columns={iconColumns}
          rows={iconRows}
          rowKey={(row) => row.key}
          emptyTitle={t("panel.keyboard.noIconYet")}
          emptyDescription={t("panel.keyboard.emojiIdHint")}
        />
      </SectionCard>

      {sections.map((section) => (
        <SectionCard key={section} title={sectionLabels(t)[section] || section}>
          <div className="space-y-2">
            {query.data?.buttons
              .filter((button) => button.section === section)
              .map((button) => (
                <ButtonEditor
                  key={button.key}
                  button={button}
                  styles={query.data?.style_options || [""]}
                  open={openKey === button.key}
                  onToggle={() => setOpenKey(openKey === button.key ? null : button.key)}
                />
              ))}
          </div>
        </SectionCard>
      ))}
    </>
  );
}

function ChipButton({ label, onClick, children }: { label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      onClick={onClick}
      className="rounded p-0.5 text-muted transition-colors hover:bg-surface-2 hover:text-text"
    >
      {children}
    </button>
  );
}

function ButtonEditor({
  button,
  styles,
  open,
  onToggle,
}: {
  button: PanelKeyboardButton;
  styles: string[];
  open: boolean;
  onToggle: () => void;
}) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState({
    text: button.text || "",
    style: button.style === "" ? "none" : button.style || "",
    icon: button.icon ? String(button.icon) : button.default_icon ? String(button.default_icon) : "",
  });
  const save = usePanelAction(panelKeyboardApi.saveButton, { invalidate: INVALIDATE });

  return (
    <div className="rounded-md border border-border">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-2 px-3 py-2.5 text-right hover:bg-surface-2"
      >
        <ChevronDown size={16} className={`shrink-0 text-muted transition-transform ${open ? "rotate-180" : ""}`} />
        <span className="flex-1 text-sm font-medium text-text">{button.title || button.key}</span>
        <code className="ltr-field hidden text-[11px] text-muted sm:inline">{button.key}</code>
        {button.blocked ? <Badge tone="warning">{t("panel.keyboard.notShown")}</Badge> : null}
        {button.style ? <Badge tone="primary">{styleLabels(t)[button.style] || button.style}</Badge> : null}
        {button.icon ? <Badge tone="success">{t("panel.keyboard.icon")}</Badge> : null}
      </button>

      {open && (
        <div className="border-t border-border p-3">
          {button.blocked && (
            <p className="mb-3 rounded-md bg-warning/10 px-3 py-2 text-xs text-warning">
              {blockedLabels(t)[button.blocked] || button.blocked}
            </p>
          )}
          <div className="grid gap-3 sm:grid-cols-3">
          <Input
            label={t("panel.common.buttonText")}
            placeholder={button.default_text || ""}
            value={draft.text}
            onChange={(event) => setDraft({ ...draft, text: event.target.value })}
          />
          <SelectField
            label={t("panel.keyboard.colour")}
            options={styles.map((value) => ({ value, label: styleLabels(t)[value] || value }))}
            value={draft.style}
            onChange={(event) => setDraft({ ...draft, style: event.target.value })}
          />
          <Input
            label={t("panel.common.premiumEmojiId")}
            ltr
            inputMode="numeric"
            placeholder={t("panel.keyboard.emptyMeansNoIcon")}
            value={draft.icon}
            onChange={(event) => setDraft({ ...draft, icon: event.target.value })}
          />
            <div className="col-span-full flex justify-end">
              <Button size="sm" loading={save.isPending} onClick={() => save.mutate({ key: button.key, ...draft })}>
                {t("common.save")}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
