import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronLeft, FolderOpen, MousePointerClick, RotateCcw, Search, SearchX, TriangleAlert, X as XIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button, ErrorState, Skeleton } from "../../components/ui";
import { panelTextsApi } from "../../api/panel";
import type { PanelTextEntry, PanelTextSection } from "../../types/panel";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { ChoiceDialog } from "./texts/ChoiceDialog";
import { canSaveText, TextEditor } from "./texts/TextEditor";

const ALL = "all";
const UNLISTED_SECTION = "unlisted";
// The bot reads its texts with lang="fa"; a new override defaults to it, an existing one keeps its own.
const DEFAULT_TEXT_LANGUAGE = "fa";
const INVALIDATE = [["texts"]];

type Filter = "all" | "set" | "unset";
type DialogState = { kind: "unsaved"; next: () => void } | { kind: "reset" } | null;

/** First non-empty line of a stored text, without the bot's markdown markers. */
function previewLine(value: string): string {
  const line = value.split("\n").find((item) => item.trim()) || "";
  return line.replace(/\[([^\]]*)\]\([^)]*\)/g, "$1").replace(/\*\*|__|~~|`|\^qc?\^|\^sp\^/g, "");
}

export default function AdminTextsPage() {
  const { t } = useTranslation();
  // Load every key once and filter on the client so search is instant.
  const query = usePanelQuery(["texts", ""], (auth) => panelTextsApi.listTexts({ ...auth, q: "" }));
  const save = usePanelAction(panelTextsApi.saveText, { invalidate: INVALIDATE });
  const remove = usePanelAction(panelTextsApi.deleteText, { invalidate: INVALIDATE });

  const [section, setSection] = useState<string>(ALL);
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [dialog, setDialog] = useState<DialogState>(null);

  const sections = useMemo(() => query.data?.sections ?? [], [query.data]);
  const allEntries = useMemo(() => sections.flatMap((item) => item.entries), [sections]);
  const selected = allEntries.find((entry) => entry.key === selectedKey) ?? null;
  const dirty = selected !== null && draft !== (selected.value || "");

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const sectionName = useCallback(
    (item: PanelTextSection) => (item.key === UNLISTED_SECTION ? t("panel.texts.otherKeys") : item.name || item.key),
    [t]
  );

  const visibleSections = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return sections
      .filter((item) => section === ALL || item.key === section)
      .map((item) => ({
        ...item,
        entries: item.entries.filter((entry) => {
          if (filter === "set" && !entry.stored) return false;
          if (filter === "unset" && entry.stored) return false;
          if (!needle) return true;
          return [entry.key, entry.title, entry.value].some((value) => (value || "").toLowerCase().includes(needle));
        }),
      }))
      .filter((item) => item.entries.length > 0);
  }, [sections, section, filter, search]);

  const saveDraft = (onDone?: () => void) => {
    if (!selected || !canSaveText(draft, selected.value || "")) return;
    // Banner fields are left out on purpose so whatever is stored stays untouched.
    save.mutate(
      { key: selected.key, value: draft, lang: selected.lang || DEFAULT_TEXT_LANGUAGE },
      { onSuccess: () => onDone?.() }
    );
  };

  function open(entry: PanelTextEntry | null) {
    setSelectedKey(entry?.key ?? null);
    setDraft(entry?.value || "");
    if (entry && window.matchMedia("(max-width: 1023px)").matches) window.scrollTo({ top: 0 });
  }

  // Every way of leaving an edited text goes through here so changes are never lost silently.
  function guard(next: () => void) {
    if (dirty) setDialog({ kind: "unsaved", next });
    else next();
  }

  if (query.isError) {
    return <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />;
  }
  if (query.isLoading || !query.data) {
    return <Skeleton className="h-64 w-full" />;
  }

  const countOf = (entries: PanelTextEntry[]) => [entries.filter((entry) => entry.stored).length, entries.length] as const;
  const [setCount, total] = countOf(allEntries);
  const percent = total ? Math.round((setCount / total) * 100) : 0;
  const sectionItems = [
    { key: ALL, label: t("panel.texts.allSections"), icon: "", counts: countOf(allEntries) },
    ...sections.map((item) => ({ key: item.key, label: sectionName(item), icon: item.icon || "", counts: countOf(item.entries) })),
  ];
  const scopeEntries = section === ALL ? allEntries : (sections.find((item) => item.key === section)?.entries ?? []);
  const [scopeSet, scopeTotal] = countOf(scopeEntries);
  const filters: { value: Filter; label: string; count: number; dot?: string }[] = [
    { value: "all", label: t("panel.texts.filterAll"), count: scopeTotal },
    { value: "set", label: t("panel.texts.filterSet"), count: scopeSet, dot: "bg-success" },
    { value: "unset", label: t("panel.texts.filterUnset"), count: scopeTotal - scopeSet, dot: "bg-border" },
  ];

  const editing = selected !== null;
  const resetFilters = () => {
    setSearch("");
    setFilter("all");
    setSection(ALL);
  };

  return (
    <>
      <div className={editing ? "hidden lg:block" : ""}>
        <PageHeader title={t("panel.common.botTexts")} subtitle={t("panel.texts.subtitle")} />
      </div>

      <div
        className={`items-center gap-3.5 rounded-2xl border border-border bg-surface px-4 py-3 ${editing ? "hidden lg:flex" : "flex"}`}
      >
        <div className="min-w-0 flex-1 text-[13px] text-text">
          <p>
            {t("panel.texts.statsSet", { count: setCount })} · {t("panel.texts.statsUnset", { count: total - setCount })}
          </p>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-2">
            <div className="h-full rounded-full bg-primary transition-all duration-300" style={{ width: `${percent}%` }} />
          </div>
        </div>
        <span className="ltr-field text-xl font-extrabold tabular-nums text-primary">{percent}%</span>
      </div>

      <div
        className={`grid grid-cols-1 items-start gap-4 lg:max-[1399px]:grid-cols-[minmax(0,1fr)_minmax(0,1.35fr)] min-[1400px]:grid-cols-[220px_minmax(0,1fr)_minmax(0,1.35fr)]`}
      >
        <nav
          aria-label={t("panel.texts.sections")}
          className={`sticky top-4 hidden rounded-2xl border border-border bg-surface p-1.5 min-[1400px]:block`}
        >
          {sectionItems.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => setSection(item.key)}
              className={`flex w-full items-center gap-2 rounded-xl px-2.5 py-2 text-start text-[13px] transition-colors ${
                section === item.key ? "bg-primary/12 font-semibold text-primary" : "text-muted hover:bg-surface-2 hover:text-text"
              }`}
            >
              <span className="shrink-0">{item.icon || <FolderOpen size={15} />}</span>
              <span className="min-w-0 flex-1 truncate">{item.label}</span>
              <span className="ltr-field shrink-0 text-[11px] tabular-nums opacity-75">
                {item.counts[0]}/{item.counts[1]}
              </span>
            </button>
          ))}
        </nav>

        <div className={`min-w-0 flex-col gap-2.5 ${editing ? "hidden lg:flex" : "flex"}`}>
          <div className="relative">
            <Search size={16} className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-muted" />
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t("panel.texts.searchPlaceholder")}
              aria-label={t("panel.common.search")}
              autoComplete="off"
              className="h-11 w-full rounded-xl border border-border bg-surface pe-10 ps-10 text-sm text-text outline-none transition-colors focus:border-primary focus:ring-4 focus:ring-primary/10"
            />
            {search && (
              <button
                type="button"
                aria-label={t("panel.texts.clearSearch")}
                onClick={() => setSearch("")}
                className="absolute left-2 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-full bg-surface-2 text-muted"
              >
                <XIcon size={14} />
              </button>
            )}
          </div>

          <div className={`no-scrollbar -mx-4 flex gap-1.5 overflow-x-auto px-4 lg:mx-0 lg:flex-wrap lg:px-0 min-[1400px]:hidden`}>
            {sectionItems.map((item) => (
              <button
                key={item.key}
                type="button"
                onClick={() => setSection(item.key)}
                className={`flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border px-3 py-1.5 text-xs transition-colors ${
                  section === item.key
                    ? "border-transparent bg-primary/12 font-semibold text-primary"
                    : "border-border bg-surface text-muted hover:text-text"
                }`}
              >
                {item.icon ? `${item.icon} ` : ""}
                {item.label}
                <span className="ltr-field text-[11px] tabular-nums opacity-75">
                  {item.counts[0]}/{item.counts[1]}
                </span>
              </button>
            ))}
          </div>

          <div className="flex gap-1 rounded-xl bg-surface-2 p-1">
            {filters.map((item) => (
              <button
                key={item.value}
                type="button"
                onClick={() => setFilter(item.value)}
                className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg px-2 py-1.5 text-xs font-medium transition-colors ${
                  filter === item.value ? "bg-surface text-text shadow-sm" : "text-muted hover:text-text"
                }`}
              >
                {item.dot && <span className={`h-[7px] w-[7px] rounded-full ${item.dot}`} />}
                {item.label}
                <span className="text-[11px] tabular-nums opacity-70">{item.count}</span>
              </button>
            ))}
          </div>
          <p className="-mt-1 px-1 text-[11.5px] leading-relaxed text-muted">{t("panel.texts.filterHint")}</p>

          {visibleSections.length === 0 ? (
            <div className="flex flex-col items-center gap-1.5 rounded-2xl border border-dashed border-border bg-surface px-5 py-10 text-center text-muted">
              <span className="mb-1.5 flex h-12 w-12 items-center justify-center rounded-xl bg-surface-2">
                <SearchX size={22} />
              </span>
              <b className="text-sm text-text">{t("panel.texts.noResults")}</b>
              <span className="text-sm">{t("panel.texts.searchEmpty")}</span>
              <Button size="sm" variant="ghost" className="mt-1.5" onClick={resetFilters}>
                {t("panel.texts.clearFilters")}
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {visibleSections.map((item) => (
                <div key={item.key}>
                  {section === ALL && (
                    <p className="flex items-center gap-1.5 px-1 pb-1.5 pt-1 text-xs font-semibold text-muted">
                      {item.icon} {sectionName(item)}
                    </p>
                  )}
                  <div className="overflow-hidden rounded-2xl border border-border bg-surface">
                    {item.entries.map((entry) => (
                      <TextRow
                        key={entry.key}
                        entry={entry}
                        active={entry.key === selectedKey}
                        onClick={() => {
                          if (entry.key !== selectedKey) guard(() => open(entry));
                        }}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className={`min-w-0 lg:sticky lg:top-4 ${editing ? "" : "hidden lg:block"}`}>
          {selected ? (
            <TextEditor
              key={selected.key}
              entry={selected}
              value={draft}
              saving={save.isPending}
              onChange={setDraft}
              onSave={() => saveDraft()}
              onBack={() => guard(() => open(null))}
              onRequestReset={() => setDialog({ kind: "reset" })}
            />
          ) : (
            <div className="flex flex-col items-center gap-1.5 rounded-2xl border border-dashed border-border bg-surface px-5 py-16 text-center text-muted">
              <span className="mb-1.5 flex h-12 w-12 items-center justify-center rounded-xl bg-surface-2">
                <MousePointerClick size={22} />
              </span>
              <b className="text-sm text-text">{t("panel.texts.selectTitle")}</b>
              <span className="text-sm">{t("panel.texts.selectHint")}</span>
            </div>
          )}
        </div>
      </div>

      <ChoiceDialog
        open={dialog?.kind === "unsaved"}
        tone="warning"
        icon={TriangleAlert}
        title={t("panel.texts.unsavedTitle")}
        text={t("panel.texts.unsavedText")}
        onClose={() => setDialog(null)}
        actions={[
          {
            label: t("panel.texts.saveAndContinue"),
            variant: "primary",
            loading: save.isPending,
            onClick: () => {
              if (dialog?.kind !== "unsaved") return;
              const next = dialog.next;
              // An empty or oversized draft cannot be saved, so continuing would drop it: keep the user here.
              if (!selected || !canSaveText(draft, selected.value || "")) {
                setDialog(null);
                return;
              }
              saveDraft(() => {
                setDialog(null);
                next();
              });
            },
          },
          {
            label: t("panel.texts.discardChanges"),
            variant: "ghost",
            onClick: () => {
              if (dialog?.kind !== "unsaved") return;
              const next = dialog.next;
              setDialog(null);
              next();
            },
          },
        ]}
      />

      <ChoiceDialog
        open={dialog?.kind === "reset"}
        tone="danger"
        icon={RotateCcw}
        title={t("panel.texts.removeSetTitle")}
        text={t("panel.texts.removeSetText")}
        onClose={() => setDialog(null)}
        actions={[
          {
            label: t("panel.texts.removeSetConfirm"),
            variant: "danger",
            loading: remove.isPending,
            onClick: () => {
              if (!selected) return;
              remove.mutate(
                { key: selected.key, lang: selected.lang || "" },
                {
                  onSuccess: () => {
                    setDraft("");
                    setDialog(null);
                  },
                }
              );
            },
          },
        ]}
      />
    </>
  );
}

function TextRow({ entry, active, onClick }: { entry: PanelTextEntry; active: boolean; onClick: () => void }) {
  const { t } = useTranslation();
  const variables = Object.keys(entry.placeholders || {}).length;
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex w-full items-center gap-3 border-b border-border px-3.5 py-3 text-start transition-colors last:border-0 ${
        active ? "bg-primary/12" : "hover:bg-surface-2"
      }`}
    >
      <span
        className={`h-2 w-2 shrink-0 rounded-full ${entry.stored ? "bg-success shadow-[0_0_0_3px] shadow-success/15" : "bg-border"}`}
      />
      <span className="min-w-0 flex-1">
        <span className={`block truncate text-sm ${active ? "font-semibold text-primary" : "font-medium text-text"}`}>
          {entry.title || entry.key}
        </span>
        <span className="block truncate text-xs text-muted">
          {entry.stored ? previewLine(entry.value || "") : t("panel.texts.unsetRow")}
        </span>
      </span>
      {variables > 0 && (
        <span className="ltr-field shrink-0 rounded-md bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-muted">{`{${variables}}`}</span>
      )}
      <ChevronLeft size={16} className="shrink-0 text-muted" />
    </button>
  );
}
