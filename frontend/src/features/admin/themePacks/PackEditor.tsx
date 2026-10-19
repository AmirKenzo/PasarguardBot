import { useEffect, useMemo, useState } from "react";
import { LayoutGrid, Plus, Trash2, TriangleAlert, Undo2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { panelThemePacksApi } from "../../../api/panel";
import { PageHeader } from "../../../components/layout/PageHeader";
import { Button, ErrorState, Input, Modal, Skeleton } from "../../../components/ui";
import type {
  ThemePackButtonEntry,
  ThemePackData,
  ThemePackItem,
  ThemePackOverviewResponse,
} from "../../../types/panel";
import { usePanelAction, usePanelQuery } from "../../../queries/usePanelApi";
import { ChoiceDialog } from "../texts/ChoiceDialog";
import { COLOUR_OPTIONS } from "../keyboard/shared";
import { KeySelector } from "./KeySelector";
import { countsLabel, issueLabel, packCounts, THEME_PACKS_QUERY_KEY } from "./shared";

const LANGS = ["fa", "en"] as const;
// Same colours as the keyboard page; "" leaves the receiver's colour alone.
const BUTTON_STYLES = ["", ...COLOUR_OPTIONS] as const;

/** The glassy look is brackets baked into the label; edit the plain label, the server adds them back. */
function plainLabel(text: string | undefined): string {
  const value = (text ?? "").trim();
  return value.startsWith("「") && value.endsWith("」") ? value.slice(1, -1).trim() : value;
}

export interface PackEditorProps {
  packId: number;
  overview: ThemePackOverviewResponse;
  onBack: () => void;
}

function clonePack(pack: ThemePackData): ThemePackData {
  return JSON.parse(JSON.stringify(pack)) as ThemePackData;
}

export function PackEditor({ packId, overview, onBack }: PackEditorProps) {
  const { t } = useTranslation();
  const query = usePanelQuery([...THEME_PACKS_QUERY_KEY, "pack", packId], (auth) =>
    panelThemePacksApi.getPack({ ...auth, pack_id: packId })
  );
  const validate = usePanelAction(panelThemePacksApi.previewPack);
  const save = usePanelAction(panelThemePacksApi.savePack, { invalidate: [THEME_PACKS_QUERY_KEY] });
  const current = usePanelAction(panelThemePacksApi.currentValues);

  const [draft, setDraft] = useState<ThemePackData | null>(null);
  const [name, setName] = useState("");
  const [issues, setIssues] = useState<Record<string, ThemePackItem>>({});
  const [adding, setAdding] = useState(false);
  const [addTexts, setAddTexts] = useState<Set<string>>(new Set());
  const [addButtons, setAddButtons] = useState<Set<string>>(new Set());
  const [confirmLeave, setConfirmLeave] = useState(false);

  useEffect(() => {
    if (!query.data) return;
    setDraft(clonePack(query.data.data));
    setName(query.data.pack?.name ?? "");
    setIssues({});
  }, [query.data]);

  const original = useMemo(() => (query.data ? JSON.stringify(query.data.data) : ""), [query.data]);
  const dirty = draft !== null && (JSON.stringify(draft) !== original || name !== (query.data?.pack?.name ?? ""));
  const textTitles = useMemo(() => new Map(overview.texts.map((entry) => [entry.key, entry.title])), [overview]);
  const buttonTitles = useMemo(() => new Map(overview.buttons.map((entry) => [entry.key, entry.title])), [overview]);

  const update = (change: (next: ThemePackData) => void) =>
    setDraft((prev) => {
      if (!prev) return prev;
      const next = clonePack(prev);
      change(next);
      return next;
    });

  const leave = () => (dirty ? setConfirmLeave(true) : onBack());

  const submit = () => {
    if (!draft) return;
    const pack = { ...draft, name: name.trim() };
    validate.mutate(
      { pack },
      {
        onSuccess: (result) => {
          const bad = result.items.filter((item) => item.status === "invalid" || item.status === "unknown");
          setIssues(Object.fromEntries(bad.map((item) => [item.id, item])));
          if (bad.length > 0) return;
          save.mutate({ pack_id: packId, name: name.trim(), pack, strict: true });
        },
      }
    );
  };

  const addFromBot = () =>
    current.mutate(
      { text_keys: [...addTexts], button_keys: [...addButtons] },
      {
        onSuccess: (result) => {
          update((next) => {
            next.texts = { ...(next.texts ?? {}), ...(result.data.texts ?? {}) };
            next.buttons = { ...(next.buttons ?? {}), ...(result.data.buttons ?? {}) };
          });
          setAdding(false);
          setAddTexts(new Set());
          setAddButtons(new Set());
        },
      }
    );

  const useCurrentLayout = () =>
    current.mutate(
      { text_keys: [], button_keys: [], include_layout: true },
      {
        onSuccess: (result) =>
          update((next) => {
            next.layout = result.data.layout;
          }),
      }
    );

  if (query.isLoading || (!draft && !query.isError)) {
    return (
      <div className="flex flex-col gap-3">
        <Skeleton className="h-12" />
        <Skeleton className="h-40" />
        <Skeleton className="h-40" />
      </div>
    );
  }
  if (query.isError || !draft) {
    return <ErrorState message={query.error?.message ?? t("apiErrors.actionFailed")} onRetry={() => void query.refetch()} />;
  }

  const textEntries = Object.entries(draft.texts ?? {}).flatMap(([key, langs]) =>
    Object.entries(langs).map(([lang, entry]) => ({ key, lang, entry }))
  );
  const buttonEntries = Object.entries(draft.buttons ?? {});
  const issueFor = (id: string) => issues[id];

  const renderIssues = (id: string) => {
    const issue = issueFor(id);
    if (!issue) return null;
    const codes = issue.status === "unknown" ? ["unknown_key"] : issue.errors;
    return (
      <p className="mt-1 flex flex-wrap items-center gap-1 text-[11px] text-danger">
        <TriangleAlert size={12} />
        {codes.map((code) => issueLabel(t, code)).join(" · ")}
      </p>
    );
  };

  return (
    <>
      <PageHeader
        title={t("panel.themePacks.editTitle")}
        subtitle={countsLabel(t, packCounts(draft))}
        back={leave}
        action={
          <Button size="sm" loading={validate.isPending || save.isPending} disabled={!dirty} onClick={submit}>
            {t("common.save")}
          </Button>
        }
      />
      <div className="flex flex-col gap-4">
        <Input label={t("panel.themePacks.name")} value={name} maxLength={100} onChange={(e) => setName(e.target.value)} />

        {Object.keys(issues).length > 0 && (
          <p className="rounded-xl bg-danger/10 px-3 py-2 text-sm text-danger">{t("panel.themePacks.fixIssues")}</p>
        )}

        <section className="rounded-2xl border border-border bg-surface">
          <header className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
            <h3 className="text-sm font-semibold text-text">
              {t("panel.themePacks.texts")} <span className="font-normal text-muted">({textEntries.length})</span>
            </h3>
            <Button size="sm" variant="secondary" onClick={() => setAdding(true)}>
              <Plus size={14} />
              {t("panel.themePacks.addFromBot")}
            </Button>
          </header>
          {textEntries.length === 0 ? (
            <p className="px-4 py-6 text-center text-sm text-muted">{t("panel.themePacks.noTexts")}</p>
          ) : (
            <ul className="divide-y divide-border">
              {textEntries.map(({ key, lang, entry }) => {
                const id = `text:${key}:${lang}`;
                const missing = LANGS.filter((code) => !draft.texts?.[key]?.[code]);
                return (
                  <li key={id} className="px-4 py-3">
                    <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
                      <span className="text-sm font-medium text-text">{textTitles.get(key) ?? key}</span>
                      <span className="ltr-field rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] uppercase text-muted">
                        {lang}
                      </span>
                      <span className="ms-auto flex gap-1">
                        {missing.map((code) => (
                          <button
                            key={code}
                            type="button"
                            className="rounded-md px-1.5 py-0.5 text-[11px] text-primary hover:bg-primary/10"
                            onClick={() =>
                              update((next) => {
                                next.texts![key]![code] = { value: entry.value };
                              })
                            }
                          >
                            + {code.toUpperCase()}
                          </button>
                        ))}
                        <button
                          type="button"
                          aria-label={t("common.delete")}
                          className="rounded-md p-1 text-danger hover:bg-danger/10"
                          onClick={() =>
                            update((next) => {
                              delete next.texts![key]![lang];
                              if (Object.keys(next.texts![key]!).length === 0) delete next.texts![key];
                            })
                          }
                        >
                          <Trash2 size={14} />
                        </button>
                      </span>
                    </div>
                    <textarea
                      value={entry.value}
                      dir={lang === "en" ? "ltr" : "rtl"}
                      onChange={(event) =>
                        update((next) => {
                          next.texts![key]![lang]!.value = event.target.value;
                        })
                      }
                      className="min-h-24 w-full resize-y rounded-xl border border-border bg-surface-2 px-3 py-2 text-sm leading-relaxed text-text outline-none focus:border-primary"
                    />
                    {renderIssues(id)}
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <section className="rounded-2xl border border-border bg-surface">
          <header className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
            <h3 className="text-sm font-semibold text-text">
              {t("panel.themePacks.buttons")} <span className="font-normal text-muted">({buttonEntries.length})</span>
            </h3>
            <Button size="sm" variant="secondary" onClick={() => setAdding(true)}>
              <Plus size={14} />
              {t("panel.themePacks.addFromBot")}
            </Button>
          </header>
          {buttonEntries.length === 0 ? (
            <p className="px-4 py-6 text-center text-sm text-muted">{t("panel.themePacks.noButtons")}</p>
          ) : (
            <ul className="divide-y divide-border">
              {buttonEntries.map(([key, entry]) => {
                const id = `button:${key}`;
                const setField = (field: keyof ThemePackButtonEntry, value: string) =>
                  update((next) => {
                    const target = next.buttons![key]!;
                    if (value) target[field] = value;
                    else delete target[field];
                  });
                return (
                  <li key={id} className="px-4 py-3">
                    <div className="mb-1.5 flex items-center gap-1.5">
                      <span className="text-sm font-medium text-text">{buttonTitles.get(key) ?? key}</span>
                      <button
                        type="button"
                        aria-label={t("common.delete")}
                        className="ms-auto rounded-md p-1 text-danger hover:bg-danger/10"
                        onClick={() =>
                          update((next) => {
                            delete next.buttons![key];
                          })
                        }
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                    <div className="grid gap-2 sm:grid-cols-[1fr_9rem_11rem]">
                      <Input
                        dense
                        value={plainLabel(entry.text)}
                        maxLength={100}
                        placeholder={t("panel.themePacks.buttonTextKeep")}
                        onChange={(event) => setField("text", event.target.value)}
                      />
                      <select
                        value={entry.style === "glass" ? "none" : (entry.style ?? "")}
                        onChange={(event) => setField("style", event.target.value)}
                        className="h-10 rounded-xl border border-border bg-surface-2 px-2 text-sm text-text outline-none focus:border-primary"
                      >
                        {BUTTON_STYLES.map((style) => (
                          <option key={style} value={style}>
                            {t(`panel.themePacks.style.${style || "keep"}`)}
                          </option>
                        ))}
                      </select>
                      <Input
                        dense
                        ltr
                        value={entry.icon ?? ""}
                        inputMode="numeric"
                        placeholder={t("panel.themePacks.iconPlaceholder")}
                        onChange={(event) => setField("icon", event.target.value.replace(/\D/g, ""))}
                      />
                    </div>
                    {renderIssues(id)}
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <section className="rounded-2xl border border-border bg-surface">
          <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-3">
            <h3 className="flex items-center gap-1.5 text-sm font-semibold text-text">
              <LayoutGrid size={15} />
              {t("panel.themePacks.layout")}
            </h3>
            <div className="flex gap-2">
              <Button size="sm" variant="secondary" loading={current.isPending} onClick={useCurrentLayout}>
                <Undo2 size={14} />
                {t("panel.themePacks.useCurrentLayout")}
              </Button>
              {draft.layout && (
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-danger"
                  onClick={() =>
                    update((next) => {
                      delete next.layout;
                    })
                  }
                >
                  <Trash2 size={14} />
                </Button>
              )}
            </div>
          </header>
          {draft.layout ? (
            <div className="flex flex-col gap-1.5 px-4 py-3">
              {draft.layout.rows.map((row, index) => (
                <div key={index} className="flex gap-1.5">
                  {row.map((key) => (
                    <span
                      key={key}
                      className={`flex-1 truncate rounded-lg border border-border px-2 py-1.5 text-center text-xs ${
                        draft.layout!.hidden.includes(key) ? "text-muted line-through" : "text-text"
                      }`}
                    >
                      {buttonTitles.get(key) ?? key}
                    </span>
                  ))}
                </div>
              ))}
              {renderIssues("layout")}
            </div>
          ) : (
            <p className="px-4 py-6 text-center text-sm text-muted">{t("panel.themePacks.noLayout")}</p>
          )}
        </section>
      </div>

      <Modal open={adding} onClose={() => setAdding(false)} title={t("panel.themePacks.addFromBot")} size="lg">
        <div className="flex flex-col gap-3 pb-1">
          <p className="text-xs text-muted">{t("panel.themePacks.addHint")}</p>
          <KeySelector
            overview={overview}
            textKeys={addTexts}
            buttonKeys={addButtons}
            onTextKeys={setAddTexts}
            onButtonKeys={setAddButtons}
            lockedTexts={new Set(Object.keys(draft.texts ?? {}))}
            lockedButtons={new Set(Object.keys(draft.buttons ?? {}))}
          />
          <div className="sticky bottom-0 -mx-5 flex justify-end gap-2 border-t border-border bg-surface px-5 py-3">
            <Button
              size="sm"
              loading={current.isPending}
              disabled={addTexts.size === 0 && addButtons.size === 0}
              onClick={addFromBot}
            >
              {t("panel.themePacks.addSelected", { count: addTexts.size + addButtons.size })}
            </Button>
          </div>
        </div>
      </Modal>

      <ChoiceDialog
        open={confirmLeave}
        tone="warning"
        icon={TriangleAlert}
        title={t("panel.themePacks.leaveTitle")}
        text={t("panel.themePacks.leaveText")}
        onClose={() => setConfirmLeave(false)}
        actions={[
          {
            label: t("panel.themePacks.discardChanges"),
            variant: "danger",
            onClick: () => {
              setConfirmLeave(false);
              onBack();
            },
          },
        ]}
      />
    </>
  );
}
