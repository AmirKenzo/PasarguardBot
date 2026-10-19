import { useState } from "react";
import { Download, FileUp, Paintbrush, Palette, Pencil, Plus, RotateCcw, Send, Shuffle, Trash2, Type } from "lucide-react";
import { useTranslation } from "react-i18next";
import { panelThemePacksApi } from "../../../api/panel";
import { useWebAppAuth } from "../../../hooks/useWebAppAuth";
import { PageHeader } from "../../../components/layout/PageHeader";
import { Badge, Button, EmptyState, ErrorState, Skeleton, Tabs } from "../../../components/ui";
import { useToast } from "../../../components/ui/Toast";
import type { ThemePackData, ThemePackLibraryEntry, ThemePackSource } from "../../../types/panel";
import { usePanelAction, usePanelQuery } from "../../../queries/usePanelApi";
import { ChoiceDialog } from "../texts/ChoiceDialog";
import { ApplyDialog } from "./ApplyDialog";
import { CreatePackDialog } from "./CreatePackDialog";
import { ImportDialog } from "./ImportDialog";
import { PackEditor } from "./PackEditor";
import { countsLabel, downloadPack, formatDate, INVALIDATE_ALL, THEME_PACKS_QUERY_KEY } from "./shared";
import { WebappThemesTab } from "./webapp/WebappThemesTab";

type PageTab = "texts" | "webapp";

const WEBAPP_TAB_HASH = "#colors";

interface ApplyState {
  title: string;
  source: ThemePackSource;
  fromFile: boolean;
}

export default function ThemePacksPage() {
  const { t, i18n } = useTranslation();
  const { auth } = useWebAppAuth();
  const toast = useToast();
  const query = usePanelQuery(THEME_PACKS_QUERY_KEY, (auth) => panelThemePacksApi.getOverview(auth));
  const remove = usePanelAction(panelThemePacksApi.deletePack, { invalidate: [THEME_PACKS_QUERY_KEY] });
  const send = usePanelAction(panelThemePacksApi.sendPack);
  const undo = usePanelAction(panelThemePacksApi.undoLastApply, { invalidate: INVALIDATE_ALL });
  const saveFile = usePanelAction(panelThemePacksApi.savePack, { invalidate: [THEME_PACKS_QUERY_KEY] });

  const [editing, setEditing] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  const [importing, setImporting] = useState(false);
  const [applying, setApplying] = useState<ApplyState | null>(null);
  const [deleting, setDeleting] = useState<ThemePackLibraryEntry | null>(null);
  const [downloading, setDownloading] = useState<number | null>(null);
  const [tab, setTab] = useState<PageTab>(() => (window.location.hash === WEBAPP_TAB_HASH ? "webapp" : "texts"));

  const overview = query.data;

  if (editing !== null && overview) {
    return <PackEditor packId={editing} overview={overview} onBack={() => setEditing(null)} />;
  }

  const download = async (pack: ThemePackLibraryEntry) => {
    if (!auth) return;
    setDownloading(pack.id);
    try {
      const detail = await panelThemePacksApi.getPack({ ...auth, pack_id: pack.id });
      downloadPack(detail.data, detail.file_name);
    } catch (error) {
      toast.show((error as Error).message || t("apiErrors.actionFailed"), "error");
    } finally {
      setDownloading(null);
    }
  };

  const saveImported = (pack: ThemePackData) =>
    saveFile.mutate(
      { pack, strict: false },
      {
        onSuccess: (result) => {
          if (result.dropped.length > 0) {
            toast.show(t("panel.themePacks.droppedOnSave", { count: result.dropped.length }), "info");
          }
          setApplying(null);
        },
      }
    );

  const last = overview?.last_import;

  const tabs = (
    <div className="mb-4">
      <Tabs
        value={tab}
        onChange={(value) => setTab(value as PageTab)}
        items={[
          { value: "texts", label: t("panel.webappThemes.tabTexts"), icon: Type },
          { value: "webapp", label: t("panel.webappThemes.tabColors"), icon: Paintbrush },
        ]}
      />
    </div>
  );

  if (tab === "webapp") {
    return (
      <>
        <PageHeader title={t("panel.themePacks.title")} subtitle={t("panel.webappThemes.subtitle")} />
        {tabs}
        <WebappThemesTab />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title={t("panel.themePacks.title")}
        subtitle={t("panel.themePacks.subtitle")}
        action={
          <div className="flex gap-2">
            <Button size="sm" variant="secondary" onClick={() => setImporting(true)} disabled={!overview}>
              <FileUp size={15} />
              <span className="hidden sm:inline">{t("panel.themePacks.import")}</span>
            </Button>
            <Button size="sm" onClick={() => setCreating(true)} disabled={!overview}>
              <Plus size={15} />
              <span className="hidden sm:inline">{t("panel.themePacks.newPack")}</span>
            </Button>
          </div>
        }
      />
      {tabs}

      {query.isLoading ? (
        <div className="grid gap-3 md:grid-cols-2">
          <Skeleton className="h-36" />
          <Skeleton className="h-36" />
        </div>
      ) : query.isError || !overview ? (
        <ErrorState message={query.error?.message ?? t("apiErrors.actionFailed")} onRetry={() => void query.refetch()} />
      ) : (
        <div className="flex flex-col gap-4">
          {last && !last.restored && (
            <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-warning/30 bg-warning/8 px-4 py-3">
              <RotateCcw size={18} className="shrink-0 text-warning" />
              <p className="min-w-0 flex-1 text-sm text-text">
                {t("panel.themePacks.lastApplied", {
                  name: last.pack_name || t("panel.themePacks.unnamed"),
                  date: formatDate(last.created_at, i18n.language),
                })}
              </p>
              <Button size="sm" variant="secondary" loading={undo.isPending} onClick={() => undo.mutate({})}>
                {t("panel.themePacks.undo")}
              </Button>
            </div>
          )}

          {overview.packs.length === 0 ? (
            <EmptyState
              icon={Palette}
              title={t("panel.themePacks.emptyTitle")}
              description={t("panel.themePacks.emptyText")}
              action={
                <Button size="sm" onClick={() => setCreating(true)}>
                  <Plus size={15} />
                  {t("panel.themePacks.newPack")}
                </Button>
              }
            />
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {overview.packs.map((pack) => (
                <article
                  key={pack.id}
                  className={`flex flex-col gap-3 rounded-2xl border bg-surface p-4 ${
                    pack.active ? "border-primary/50 shadow-[0_0_0_3px] shadow-primary/10" : "border-border"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/12 text-primary">
                      <Palette size={20} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <h3 className="truncate text-sm font-semibold text-text">{pack.name}</h3>
                        {pack.active && <Badge tone="success">{t("panel.themePacks.active")}</Badge>}
                      </div>
                      <p className="mt-0.5 text-xs text-muted">{countsLabel(t, pack.counts)}</p>
                      <p className="text-[11px] text-muted">
                        {t("panel.themePacks.updated", { date: formatDate(pack.updated_at, i18n.language) })}
                        {pack.source_bot ? ` · ${pack.source_bot}` : ""}
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    <Button
                      size="sm"
                      onClick={() =>
                        setApplying({
                          title: t("panel.themePacks.switchTitle", { name: pack.name }),
                          source: { pack_id: pack.id },
                          fromFile: false,
                        })
                      }
                    >
                      <Shuffle size={14} />
                      {t("panel.themePacks.switch")}
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => setEditing(pack.id)}>
                      <Pencil size={14} />
                      {t("common.edit")}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      loading={downloading === pack.id}
                      onClick={() => void download(pack)}
                      aria-label={t("panel.themePacks.download")}
                    >
                      <Download size={14} />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      loading={send.isPending && send.variables?.pack_id === pack.id}
                      onClick={() => send.mutate({ pack_id: pack.id })}
                      aria-label={t("panel.themePacks.sendTelegram")}
                      title={t("panel.themePacks.sendTelegram")}
                    >
                      <Send size={14} />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="ms-auto text-danger hover:bg-danger/10"
                      onClick={() => setDeleting(pack)}
                      aria-label={t("common.delete")}
                    >
                      <Trash2 size={14} />
                    </Button>
                  </div>
                </article>
              ))}
            </div>
          )}
          <p className="text-xs text-muted">{t("panel.themePacks.shareHint")}</p>
        </div>
      )}

      {overview && (
        <CreatePackDialog
          open={creating}
          overview={overview}
          onClose={() => setCreating(false)}
          onCreated={(packId) => {
            setCreating(false);
            setEditing(packId);
          }}
        />
      )}

      <ImportDialog
        open={importing}
        onClose={() => setImporting(false)}
        onLoaded={(pack) => {
          setImporting(false);
          setApplying({
            title: pack.name ? t("panel.themePacks.importNamed", { name: pack.name }) : t("panel.themePacks.importTitle"),
            source: { pack },
            fromFile: true,
          });
        }}
      />

      {applying && (
        <ApplyDialog
          open
          title={applying.title}
          source={applying.source}
          onSaveToLibrary={applying.fromFile ? saveImported : undefined}
          savePending={saveFile.isPending}
          onClose={() => setApplying(null)}
        />
      )}

      <ChoiceDialog
        open={deleting !== null}
        tone="danger"
        icon={Trash2}
        title={t("panel.themePacks.deleteTitle")}
        text={t("panel.themePacks.deleteText", { name: deleting?.name ?? "" })}
        onClose={() => setDeleting(null)}
        actions={[
          {
            label: t("common.delete"),
            variant: "danger",
            loading: remove.isPending,
            onClick: () => {
              if (!deleting) return;
              remove.mutate({ pack_id: deleting.id }, { onSuccess: () => setDeleting(null) });
            },
          },
        ]}
      />
    </>
  );
}
