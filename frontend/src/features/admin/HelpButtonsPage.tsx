import { useEffect, useMemo, useRef, useState } from "react";
import { LayoutGrid, Link2, MessageSquareText, Package, PackagePlus, RefreshCw } from "lucide-react";
import { useTranslation } from "react-i18next";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button, ErrorState, Sheet, Skeleton, Tabs } from "../../components/ui";
import { panelHelpButtonsApi } from "../../api/panel";
import { useIsDesktop } from "../../hooks/useMediaQuery";
import type { HelpButtonKind, PanelHelpPreset } from "../../types/panel";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { SyncTab } from "./helpButtons/SyncTab";
import { ButtonEditor } from "./helpButtons/ButtonEditor";
import { HelpPreview, LayoutEditor } from "./helpButtons/LayoutEditor";
import { HELP_INVALIDATE, HELP_QUERY_KEY, layoutSignature, mergeLayout } from "./helpButtons/shared";

type TabKey = "layout" | "sync";
/** What the editor shows: an existing button, or a new one of a kind. */
type Editing = { id: number } | { kind: HelpButtonKind } | null;

export default function AdminHelpButtonsPage() {
  const { t } = useTranslation();
  const isDesktop = useIsDesktop();
  const query = usePanelQuery(HELP_QUERY_KEY, (auth) => panelHelpButtonsApi.getHelpButtons(auth), {
    // Follow a running sync until it reports back.
    refetchInterval: (q) => (q.state.data?.sync.running ? 3000 : false),
  });
  const saveLayout = usePanelAction(panelHelpButtonsApi.saveLayout, { invalidate: HELP_INVALIDATE });

  const [tab, setTab] = useState<TabKey>("layout");
  const [layout, setLayout] = useState<number[][]>([]);
  const [editing, setEditing] = useState<Editing>(null);
  const [presetsOpen, setPresetsOpen] = useState(false);

  const buttons = useMemo(
    () => new Map((query.data?.buttons || []).map((button) => [button.id, button])),
    [query.data]
  );
  const serverLayout = useMemo(() => query.data?.layout || [], [query.data]);
  const serverSignature = query.data ? layoutSignature(serverLayout) : "";

  // A refetch after a button edit must not wipe unsaved moves: merge instead of replacing.
  const lastSignature = useRef<string | null>(null);
  useEffect(() => {
    if (!query.data || serverSignature === lastSignature.current) return;
    const first = lastSignature.current === null;
    lastSignature.current = serverSignature;
    setLayout((draft) => (first ? serverLayout : mergeLayout(draft, serverLayout, new Set(buttons.keys()))));
  }, [query.data, serverSignature, serverLayout, buttons]);

  const dirty = Boolean(serverSignature) && layoutSignature(layout) !== serverSignature;

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  if (query.isError) return <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />;
  if (query.isLoading || !query.data) return <Skeleton className="h-64 w-full" />;

  const selectedId = editing && "id" in editing ? editing.id : null;
  const editingButton = selectedId != null ? buttons.get(selectedId) ?? null : null;
  const editingKind: HelpButtonKind | null = editing ? ("kind" in editing ? editing.kind : editingButton?.kind ?? null) : null;

  const editor = editing && editingKind && (selectedId == null || editingButton) && (
    <ButtonEditor
      key={selectedId ?? `new-${editingKind}`}
      button={editingButton}
      kind={editingKind}
      onSaved={(id) => setEditing(id != null ? { id } : null)}
      onDeleted={() => setEditing(null)}
      onClose={() => setEditing(null)}
    />
  );

  const addButtons: { kind: HelpButtonKind; icon: typeof Link2; label: string }[] = [
    { kind: "link", icon: Link2, label: t("panel.helpButtons.addLink") },
    { kind: "app", icon: Package, label: t("panel.helpButtons.addApp") },
    { kind: "text", icon: MessageSquareText, label: t("panel.helpButtons.addText") },
  ];

  return (
    <>
      <PageHeader title={t("panel.helpButtons.title")} subtitle={t("panel.helpButtons.subtitle")} />

      <div className="mb-4">
        <Tabs
          items={[
            { value: "layout", label: `${t("panel.helpButtons.tabLayout")} · ${buttons.size}`, icon: LayoutGrid },
            { value: "sync", label: t("panel.helpButtons.tabSync"), icon: RefreshCw },
          ]}
          value={tab}
          onChange={(value) => setTab(value as TabKey)}
        />
      </div>

      {tab === "sync" && <SyncTab state={query.data.sync} />}

      {tab === "layout" && (
        <div className="grid gap-4 lg:grid-cols-2 lg:items-start">
          <div className="space-y-4">
            <HelpPreview layout={layout} buttons={buttons} />

            <div className="space-y-3 rounded-sm border border-border bg-surface p-3 sm:p-4">
              <LayoutEditor
                layout={layout}
                buttons={buttons}
                selected={selectedId}
                onSelect={(id) => setEditing({ id })}
                onLayoutChange={setLayout}
              />
              <div className="flex flex-wrap gap-2 border-t border-border pt-3">
                {addButtons.map(({ kind, icon: Icon, label }) => (
                  <Button key={kind} size="sm" variant="secondary" onClick={() => setEditing({ kind })}>
                    <Icon size={14} />
                    {label}
                  </Button>
                ))}
                {query.data.presets.length > 0 && (
                  <Button size="sm" variant="ghost" onClick={() => setPresetsOpen(true)}>
                    <PackagePlus size={14} />
                    {t("panel.helpButtons.addPresets")}
                  </Button>
                )}
              </div>
            </div>
            {dirty && (
              <div className="flex items-center justify-between gap-2 rounded-sm border border-warning/40 bg-surface/95 px-3 py-2 sm:px-4">
                <span className="flex min-w-0 items-center gap-2 text-xs font-medium text-warning sm:text-sm">
                  <span className="h-2 w-2 shrink-0 animate-pulse rounded-full bg-warning" />
                  <span className="truncate">{t("panel.keyboard.unsavedLayout")}</span>
                </span>
                <div className="flex shrink-0 gap-1.5">
                  <Button size="sm" variant="ghost" onClick={() => setLayout(serverLayout)}>
                    {t("panel.keyboard.discard")}
                  </Button>
                  <Button size="sm" loading={saveLayout.isPending} onClick={() => saveLayout.mutate({ layout })}>
                    {t("panel.keyboard.saveLayout")}
                  </Button>
                </div>
              </div>
            )}
          </div>

          {isDesktop ? (
            <div className="rounded-sm border border-border bg-surface p-3 sm:p-4">
              {editor || (
                <p className="py-8 text-center text-sm text-muted">{t("panel.helpButtons.selectHint")}</p>
              )}
            </div>
          ) : (
            <Sheet open={Boolean(editor)} onClose={() => setEditing(null)}>
              {editor}
            </Sheet>
          )}
        </div>
      )}

      <PresetsSheet open={presetsOpen} presets={query.data.presets} onClose={() => setPresetsOpen(false)} />

    </>
  );
}

function PresetsSheet({ open, presets, onClose }: { open: boolean; presets: PanelHelpPreset[]; onClose: () => void }) {
  const { t } = useTranslation();
  const [picked, setPicked] = useState<string[]>([]);
  const add = usePanelAction(panelHelpButtonsApi.addPresets, { invalidate: HELP_INVALIDATE });
  const toggle = (key: string) =>
    setPicked((current) => (current.includes(key) ? current.filter((k) => k !== key) : [...current, key]));

  return (
    <Sheet open={open} onClose={onClose} title={t("panel.helpButtons.addPresets")}>
      <p className="mb-3 text-xs leading-relaxed text-muted">{t("panel.helpButtons.presetsHint")}</p>
      <div className="space-y-2">
        {presets.map((preset) => (
          <label
            key={preset.key}
            className="flex cursor-pointer items-center gap-3 rounded-md border border-border p-3 hover:bg-surface-2"
          >
            <input
              type="checkbox"
              checked={picked.includes(preset.key)}
              onChange={() => toggle(preset.key)}
              className="h-4 w-4 accent-[rgb(var(--c-primary-rgb))]"
            />
            <span className="min-w-0">
              <span className="block text-sm font-medium text-text">{preset.name}</span>
              <span className="ltr-field block truncate text-xs text-muted">{preset.repo}</span>
            </span>
          </label>
        ))}
      </div>
      <div className="mt-4">
        <Button
          fullWidth
          disabled={picked.length === 0}
          loading={add.isPending}
          onClick={() =>
            add.mutate(
              { keys: picked },
              {
                onSuccess: () => {
                  setPicked([]);
                  onClose();
                },
              }
            )
          }
        >
          {t("panel.helpButtons.addSelected", { count: picked.length })}
        </Button>
      </div>
    </Sheet>
  );
}

