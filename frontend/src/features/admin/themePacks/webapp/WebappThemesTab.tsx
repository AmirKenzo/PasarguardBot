import { useMemo, useState } from "react";
import { Check, FileUp, Moon, Pencil, Plus, RotateCcw, Share2, Sparkles, Sun, Trash2, Wand2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { panelWebappThemesApi } from "../../../../api/panel";
import { Button, Card, ChipTabs, ErrorState, Skeleton } from "../../../../components/ui";
import { Toggle } from "../../components/Toggle";
import { useTheme } from "../../../../design/ThemeProvider";
import { DEFAULT_THEME, generateTheme } from "../../../../design/webappThemes";
import type { Scheme } from "../../../../design/webappThemes";
import { usePanelAction, usePanelQuery } from "../../../../queries/usePanelApi";
import type { WebappThemeMode } from "../../../../types/panel";
import { ChoiceDialog } from "../../texts/ChoiceDialog";
import { ImportThemeDialog } from "./ImportThemeDialog";
import type { ParsedShare } from "./shared";
import { CUSTOM_PREFIX, WEBAPP_THEMES_QUERY_KEY, buildLibrary, cloneTheme, swatches } from "./shared";
import type { LibraryTheme } from "./shared";
import { ShareThemeDialog } from "./ShareThemeDialog";
import { ThemeEditor } from "./ThemeEditor";
import type { ThemeDraft } from "./ThemeEditor";
import { ThemePreviewPhone } from "./ThemePreviewPhone";
import { ThemeThumb } from "./ThemeThumb";

type Filter = "all" | "mine" | "presets";

interface PreviousState {
  mode: WebappThemeMode;
  active: string;
}

export function WebappThemesTab() {
  const { t } = useTranslation();
  const { scheme: appScheme, reloadConfig } = useTheme();
  const query = usePanelQuery(WEBAPP_THEMES_QUERY_KEY, (auth) => panelWebappThemesApi.getOverview(auth));
  const invalidate = { invalidate: [WEBAPP_THEMES_QUERY_KEY] };
  const activate = usePanelAction(panelWebappThemesApi.activateTheme, invalidate);
  const options = usePanelAction(panelWebappThemesApi.updateOptions, invalidate);
  const save = usePanelAction(panelWebappThemesApi.saveTheme, invalidate);
  const remove = usePanelAction(panelWebappThemesApi.deleteTheme, invalidate);

  const [previewKey, setPreviewKey] = useState<string | null>(null);
  const [scheme, setScheme] = useState<Scheme>(appScheme);
  const [draft, setDraft] = useState<ThemeDraft | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [sharing, setSharing] = useState<LibraryTheme | null>(null);
  const [importing, setImporting] = useState(false);
  const [deleting, setDeleting] = useState<LibraryTheme | null>(null);
  const [previous, setPrevious] = useState<PreviousState | null>(null);

  const overview = query.data;
  const library = useMemo(() => buildLibrary(t, overview?.themes ?? []), [t, overview?.themes]);
  const k = (key: string, values?: Record<string, unknown>) => t(`panel.webappThemes.${key}`, values);

  if (query.isLoading) {
    return (
      <div className="grid gap-3 md:grid-cols-2">
        <Skeleton className="h-36" />
        <Skeleton className="h-36" />
      </div>
    );
  }
  if (query.isError || !overview) {
    return <ErrorState message={query.error?.message ?? t("apiErrors.actionFailed")} onRetry={() => void query.refetch()} />;
  }

  const byKey = (key: string) => library.find((item) => item.key === key);
  const activeItem = byKey(overview.active);
  const previewItem = byKey(previewKey ?? overview.active) ?? activeItem ?? library[0];
  const previewTheme = draft?.theme ?? previewItem?.theme ?? DEFAULT_THEME;
  const visible = library.filter((item) =>
    filter === "all" ? true : filter === "mine" ? item.kind !== "preset" : item.kind === "preset"
  );
  const ownCount = library.filter((item) => item.kind !== "preset").length;

  const afterChange = () => void reloadConfig();

  const activateItem = (item: LibraryTheme) => {
    const before: PreviousState = { mode: overview.mode, active: overview.active };
    activate.mutate(
      { active: item.key, theme: item.theme },
      {
        onSuccess: () => {
          setPrevious(before);
          setPreviewKey(item.key);
          afterChange();
        },
      }
    );
  };

  const undoSwitch = () => {
    if (!previous) return;
    const target = byKey(previous.active) ?? byKey("default");
    if (!target) return;
    activate.mutate(
      { active: target.key, theme: target.theme },
      {
        onSuccess: () => {
          if (previous.mode === "telegram") options.mutate({ mode: "telegram" }, { onSuccess: afterChange });
          else afterChange();
          setPrevious(null);
        },
      }
    );
  };

  const setMode = (mode: WebappThemeMode) => {
    if (mode === overview.mode) return;
    if (mode === "custom") {
      // Switching on custom colors applies whatever theme is marked active.
      const target = activeItem ?? byKey("default");
      if (target) activateItem(target);
      return;
    }
    options.mutate({ mode }, { onSuccess: afterChange });
  };

  const startEdit = (item: LibraryTheme | null) => {
    if (!item) {
      setDraft({ themeId: null, name: k("newName"), theme: generateTheme({ hue: 212 }), dirty: true });
    } else if (item.entry) {
      setDraft({ themeId: item.entry.id, name: item.name, theme: cloneTheme(item.theme), dirty: false });
    } else {
      setDraft({ themeId: null, name: k("copyName", { name: item.name }), theme: cloneTheme(item.theme), dirty: true });
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const saveDraft = (andActivate: boolean) => {
    if (!draft) return;
    const name = draft.name.trim() || k("newName");
    save.mutate(
      { theme_id: draft.themeId, name, theme: draft.theme },
      {
        onSuccess: (result) => {
          setDraft(null);
          if (!result.theme_id) return;
          const key = `${CUSTOM_PREFIX}${result.theme_id}`;
          setPreviewKey(key);
          if (andActivate) {
            activateItem({ key, name, theme: draft.theme, kind: "custom" });
          } else if (overview.active === key) {
            afterChange();
          }
        },
      }
    );
  };

  const importShare = (share: ParsedShare, andActivate: boolean) => {
    const name = share.name.trim() || k("import.defaultName");
    save.mutate(
      { name, theme: share.theme, source_bot: share.sourceBot, imported: true },
      {
        onSuccess: (result) => {
          setImporting(false);
          if (!result.theme_id) return;
          const key = `${CUSTOM_PREFIX}${result.theme_id}`;
          setPreviewKey(key);
          if (andActivate) activateItem({ key, name, theme: share.theme, kind: "imported" });
        },
      }
    );
  };

  const kindLabel = (item: LibraryTheme) =>
    item.kind === "preset" ? k("kindPreset") : item.kind === "imported" ? k("kindImported") : k("kindCustom");

  return (
    <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
      <div className="flex min-w-0 flex-col gap-4">
        <Card className="flex flex-col gap-4 p-4 sm:p-5">
          <div>
            <h2 className="font-semibold text-text">{k("sourceTitle")}</h2>
            <p className="text-xs text-muted">{k("sourceText")}</p>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {(["telegram", "custom"] as const).map((mode) => {
              const selected = overview.mode === mode;
              return (
                <button
                  key={mode}
                  type="button"
                  aria-pressed={selected}
                  disabled={activate.isPending || options.isPending}
                  onClick={() => setMode(mode)}
                  className={`flex items-start gap-3 rounded-md border-[1.5px] p-3 text-start transition-colors disabled:opacity-60 ${
                    selected ? "border-primary bg-primary/6" : "border-border bg-surface hover:border-primary/40"
                  }`}
                >
                  <span
                    className={`mt-0.5 flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-full border-2 ${
                      selected ? "border-primary" : "border-border"
                    }`}
                  >
                    {selected && <span className="h-2 w-2 rounded-full bg-primary" />}
                  </span>
                  <span className="min-w-0">
                    <span className="block text-sm font-semibold text-text">{k(`mode.${mode}`)}</span>
                    <span className="block text-xs text-muted">
                      {mode === "custom"
                        ? k("mode.customText", { name: activeItem?.name ?? k("mode.none") })
                        : k("mode.telegramText")}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
          <div className="flex flex-col gap-3 border-t border-dashed border-border pt-4">
            <Toggle
              checked={overview.user_scheme}
              disabled={options.isPending}
              onChange={(value) => options.mutate({ user_scheme: value }, { onSuccess: afterChange })}
              label={k("userScheme")}
              hint={k("userSchemeText")}
            />
            <Toggle
              checked={overview.user_pick}
              disabled={options.isPending}
              onChange={(value) => options.mutate({ user_pick: value }, { onSuccess: afterChange })}
              label={k("userPick")}
              hint={k("userPickText")}
            />
          </div>
        </Card>

        {previous && !draft && (
          <div className="flex flex-wrap items-center gap-3 rounded-md border border-success/30 bg-success/8 px-4 py-3">
            <Check size={18} className="shrink-0 text-success" />
            <p className="min-w-0 flex-1 text-sm text-text">{k("switched", { name: activeItem?.name ?? "" })}</p>
            <Button size="sm" variant="secondary" loading={activate.isPending} onClick={undoSwitch}>
              <RotateCcw size={14} />
              {k("undo")}
            </Button>
          </div>
        )}

        {draft ? (
          <ThemeEditor
            draft={draft}
            scheme={scheme}
            onSchemeChange={setScheme}
            onChange={setDraft}
            onCancel={() => setDraft(null)}
            onSave={saveDraft}
            saving={save.isPending || activate.isPending}
          />
        ) : (
          <Card className="flex flex-col gap-4 p-4 sm:p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="font-semibold text-text">{k("libraryTitle")}</h2>
                <p className="text-xs text-muted">{k("libraryText", { count: ownCount, max: overview.max_themes })}</p>
              </div>
              <div className="flex gap-2">
                <Button size="sm" variant="secondary" onClick={() => setImporting(true)}>
                  <FileUp size={15} />
                  {k("import.button")}
                </Button>
                <Button size="sm" onClick={() => startEdit(null)}>
                  <Plus size={15} />
                  {k("newTheme")}
                </Button>
              </div>
            </div>

            <ChipTabs<Filter>
              value={filter}
              onChange={setFilter}
              options={[
                { value: "all", label: k("filterAll"), count: library.length },
                { value: "mine", label: k("filterMine"), count: ownCount },
                { value: "presets", label: k("filterPresets"), count: library.length - ownCount },
              ]}
            />

            <div className="grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-3">
              {filter !== "presets" && (
                <button
                  type="button"
                  onClick={() => startEdit(null)}
                  className="flex min-h-[184px] flex-col items-center justify-center gap-2 rounded-md border-[1.5px] border-dashed border-border text-sm font-semibold text-muted transition-colors hover:border-primary hover:text-primary"
                >
                  <Wand2 size={22} />
                  {k("fromColor")}
                </button>
              )}
              {visible.map((item) => {
                const isActive = overview.mode === "custom" && item.key === overview.active;
                const isPreview = item.key === previewItem?.key;
                return (
                  <article
                    key={item.key}
                    className={`flex flex-col overflow-hidden rounded-md border-[1.5px] bg-surface transition-colors ${
                      isPreview ? "border-primary" : "border-border"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => setPreviewKey(item.key)}
                      aria-label={k("previewOf", { name: item.name })}
                    >
                      <ThemeThumb theme={item.theme} />
                    </button>
                    <div className="flex flex-1 flex-col gap-2 p-2.5">
                      <div className="flex items-center justify-between gap-1.5">
                        <h3 className="truncate text-sm font-semibold text-text">{item.name}</h3>
                        <span className="flex shrink-0 gap-0.5">
                          {swatches(item.theme.light).map((color, index) => (
                            <span
                              key={index}
                              className="h-3.5 w-3.5 rounded-full ring-1 ring-inset ring-black/10"
                              style={{ background: color }}
                            />
                          ))}
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {isActive && (
                          <span className="rounded-full bg-success/14 px-2 py-0.5 text-3xs font-semibold text-success">
                            {k("activeBadge")}
                          </span>
                        )}
                        <span
                          className={`rounded-full bg-surface-2 px-2 py-0.5 text-3xs font-semibold ${
                            item.kind === "imported" ? "text-primary" : "text-muted"
                          }`}
                        >
                          {kindLabel(item)}
                        </span>
                        {item.entry?.source_bot && item.kind === "imported" && (
                          <span className="rounded-full bg-surface-2 px-2 py-0.5 text-3xs font-semibold text-muted">
                            {item.entry.source_bot}
                          </span>
                        )}
                      </div>
                      <div className="mt-auto flex flex-wrap gap-1">
                        {isActive ? (
                          <Button size="sm" variant="secondary" disabled>
                            <Check size={14} />
                            {k("activeBadge")}
                          </Button>
                        ) : (
                          <Button
                            size="sm"
                            loading={activate.isPending && activate.variables?.active === item.key}
                            onClick={() => activateItem(item)}
                          >
                            {k("activate")}
                          </Button>
                        )}
                        <Button size="sm" variant="ghost" onClick={() => startEdit(item)} aria-label={t("common.edit")}>
                          <Pencil size={14} />
                        </Button>
                        {item.entry && (
                          <>
                            <Button size="sm" variant="ghost" onClick={() => setSharing(item)} aria-label={k("shareAction")}>
                              <Share2 size={14} />
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="text-danger hover:bg-danger/10"
                              onClick={() => setDeleting(item)}
                              aria-label={t("common.delete")}
                            >
                              <Trash2 size={14} />
                            </Button>
                          </>
                        )}
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
            <p className="flex items-start gap-1.5 text-xs text-muted">
              <Sparkles size={14} className="mt-0.5 shrink-0" />
              {k("presetHint")}
            </p>
          </Card>
        )}
      </div>

      <aside className="order-first flex flex-col items-center gap-2.5 lg:sticky lg:top-4 lg:order-none">
        <div className="flex w-full max-w-[340px] items-center justify-between gap-2">
          <span className="truncate text-xs font-semibold text-muted">
            {draft
              ? k("previewEditing", { name: draft.name || k("newName") })
              : k("previewOfLabel", { name: previewItem?.name ?? "" })}
          </span>
          <div className="inline-flex shrink-0 rounded-md border border-border bg-surface-2 p-1">
            {(["light", "dark"] as const).map((value) => (
              <button
                key={value}
                type="button"
                aria-pressed={scheme === value}
                aria-label={k(value)}
                onClick={() => setScheme(value)}
                className={`flex items-center gap-1 rounded-sm px-2.5 py-1 text-xs font-semibold ${
                  scheme === value ? "bg-surface text-text shadow-sm" : "text-muted"
                }`}
              >
                {value === "light" ? <Sun size={13} /> : <Moon size={13} />}
                {k(value)}
              </button>
            ))}
          </div>
        </div>
        <ThemePreviewPhone theme={previewTheme} scheme={scheme} />
        <p className="max-w-[340px] text-center text-2xs text-muted">
          {overview.mode === "telegram" && !draft ? k("previewTelegramNote") : k("previewNote")}
        </p>
      </aside>

      <ShareThemeDialog item={sharing} onClose={() => setSharing(null)} />
      <ImportThemeDialog
        open={importing}
        onClose={() => setImporting(false)}
        onImport={importShare}
        saving={save.isPending || activate.isPending}
      />
      <ChoiceDialog
        open={deleting !== null}
        tone="danger"
        icon={Trash2}
        title={k("deleteTitle")}
        text={
          deleting && overview.mode === "custom" && deleting.key === overview.active
            ? k("deleteActiveText", { name: deleting.name })
            : k("deleteText", { name: deleting?.name ?? "" })
        }
        onClose={() => setDeleting(null)}
        actions={[
          {
            label: t("common.delete"),
            variant: "danger",
            loading: remove.isPending,
            onClick: () => {
              const target = deleting?.entry;
              if (!target) return;
              remove.mutate(
                { theme_id: target.id },
                {
                  onSuccess: () => {
                    if (previewKey === deleting?.key) setPreviewKey(null);
                    setDeleting(null);
                    afterChange();
                  },
                }
              );
            },
          },
        ]}
      />
    </div>
  );
}
