import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { LayoutGrid, Sparkles, Type } from "lucide-react";
import { useTranslation } from "react-i18next";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button, ErrorState, Skeleton, Tabs } from "../../components/ui";
import { panelKeyboardApi } from "../../api/panel";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { ButtonsTab } from "./keyboard/ButtonsTab";
import { EmojiTab } from "./keyboard/EmojiTab";
import { LayoutTab, toRows } from "./keyboard/LayoutTab";
import type { LayoutRow } from "./keyboard/LayoutTab";
import { INVALIDATE, KEYBOARD_QUERY_KEY } from "./keyboard/shared";
import type { TabKey } from "./keyboard/shared";

/** Stable fingerprint of a layout, ignoring empty rows the save endpoint drops anyway. */
function layoutSignature(layout: string[][], hidden: string[]): string {
  return JSON.stringify([layout.filter((row) => row.length > 0), [...hidden].sort()]);
}

export default function AdminKeyboardPage() {
  const { t } = useTranslation();
  const query = usePanelQuery(KEYBOARD_QUERY_KEY, (auth) => panelKeyboardApi.getKeyboard(auth));
  const saveLayout = usePanelAction(panelKeyboardApi.saveLayout, { invalidate: INVALIDATE });
  const resetLayout = usePanelAction(panelKeyboardApi.resetLayout, { invalidate: INVALIDATE });

  const [tab, setTab] = useState<TabKey>("layout");
  const [rows, setRows] = useState<LayoutRow[]>([]);
  const [hidden, setHidden] = useState<string[]>([]);
  const [focusKey, setFocusKey] = useState<string | null>(null);

  const serverHidden = useMemo(
    () => (query.data ? query.data.buttons.filter((button) => button.hidden).map((button) => button.key) : []),
    [query.data]
  );

  const resetDraft = useCallback(() => {
    if (!query.data) return;
    setRows(toRows(query.data.layout));
    setHidden(serverHidden);
  }, [query.data, serverHidden]);

  // Refetches after a button edit must not wipe an unsaved layout; only a changed server layout resets it.
  const serverSignature = query.data ? layoutSignature(query.data.layout, serverHidden) : "";
  const lastServerSignature = useRef<string | null>(null);
  useEffect(() => {
    if (!serverSignature || serverSignature === lastServerSignature.current) return;
    lastServerSignature.current = serverSignature;
    resetDraft();
  }, [serverSignature, resetDraft]);

  const layout = rows.map((row) => row.keys);
  const dirty = Boolean(serverSignature) && layoutSignature(layout, hidden) !== serverSignature;

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const clearFocus = useCallback(() => setFocusKey(null), []);

  if (query.isError) {
    return <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />;
  }
  if (query.isLoading || !query.data) {
    return <Skeleton className="h-64 w-full" />;
  }

  const iconCount = query.data.buttons.filter((button) => button.icon != null).length;
  const tabs = [
    { value: "layout", label: t("panel.keyboard.tabLayout"), icon: LayoutGrid },
    { value: "buttons", label: `${t("panel.keyboard.tabButtons")} · ${query.data.buttons.length}`, icon: Type },
    { value: "emoji", label: `${t("panel.common.premiumEmoji")} · ${iconCount}`, icon: Sparkles },
  ];

  return (
    <>
      <PageHeader title={t("panel.common.keyboardLayout")} subtitle={t("panel.keyboard.subtitle")} />

      <div className="mb-4">
        <Tabs items={tabs} value={tab} onChange={(value) => setTab(value as TabKey)} />
      </div>

      {tab === "layout" && (
        <LayoutTab
          data={query.data}
          rows={rows}
          hidden={hidden}
          onRowsChange={setRows}
          onHiddenChange={setHidden}
          onEditButton={(key) => {
            setFocusKey(key);
            setTab("buttons");
          }}
          onReset={() => resetLayout.mutate({})}
          resetting={resetLayout.isPending}
        />
      )}
      {tab === "buttons" && <ButtonsTab data={query.data} focusKey={focusKey} onFocusHandled={clearFocus} />}
      {tab === "emoji" && <EmojiTab data={query.data} />}

      {dirty && (
        <div className="sticky bottom-3 z-20 mt-4 flex items-center justify-between gap-2 rounded-xl border border-warning/40 bg-surface/95 px-3 py-2 shadow-lg backdrop-blur sm:px-4">
          <span className="flex min-w-0 items-center gap-2 text-xs font-medium text-warning sm:text-sm">
            <span className="h-2 w-2 shrink-0 animate-pulse rounded-full bg-warning" />
            <span className="truncate">{t("panel.keyboard.unsavedLayout")}</span>
          </span>
          <div className="flex shrink-0 gap-1.5">
            <Button size="sm" variant="ghost" onClick={resetDraft}>
              {t("panel.keyboard.discard")}
            </Button>
            <Button size="sm" loading={saveLayout.isPending} onClick={() => saveLayout.mutate({ layout, hidden })}>
              {t("panel.keyboard.saveLayout")}
            </Button>
          </div>
        </div>
      )}
    </>
  );
}
