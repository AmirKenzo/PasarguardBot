import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge, Button, ErrorState, Input, Skeleton } from "../../components/ui";
import { panelTextsApi } from "../../api/panel";
import type { PanelTextEntry } from "../../types/panel";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { ConfirmButton, SectionCard, SelectField, Toolbar } from "./components";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

const positionLabels = (t: TFunction): Record<string, string> => ({
  "": t("panel.texts.noBanner"),
  top: t("panel.texts.bannerAbove"),
  bottom: t("panel.texts.bannerBelow"),
});

export default function AdminTextsPage() {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const [draftSearch, setDraftSearch] = useState("");
  const [openKey, setOpenKey] = useState<string | null>(null);

  const query = usePanelQuery(["texts", search], (auth) => panelTextsApi.listTexts({ ...auth, q: search }));

  return (
    <>
      <PageHeader title={t("panel.common.botTexts")} subtitle={t("panel.texts.fallbackNote")} />

      <Toolbar onSubmit={() => setSearch(draftSearch)}>
        <div className="min-w-[14rem] flex-1">
          <Input
            label={t("panel.common.search")}
            value={draftSearch}
            onChange={(event) => setDraftSearch(event.target.value)}
            placeholder={t("panel.texts.searchPlaceholder")}
          />
        </div>
        <Button size="md" type="submit" variant="secondary">
          {t("panel.common.search")}
        </Button>
      </Toolbar>

      {query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : query.isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : query.data?.sections.length ? (
        query.data.sections.map((section) => (
          <SectionCard
            key={section.key}
            title={`${section.icon || ""} ${section.name || section.key}`.trim()}
            description={t("panel.texts.keyCount", { count: section.entries.length })}
          >
            <div className="space-y-2">
              {section.entries.map((entry) => (
                <TextEditor
                  key={entry.key}
                  entry={entry}
                  positions={query.data?.banner_positions || [""]}
                  open={openKey === entry.key}
                  onToggle={() => setOpenKey(openKey === entry.key ? null : entry.key)}
                />
              ))}
            </div>
          </SectionCard>
        ))
      ) : (
        <SectionCard title={t("panel.texts.noResults")}>
          <p className="py-4 text-center text-sm text-muted">{t("panel.texts.searchEmpty")}</p>
        </SectionCard>
      )}
    </>
  );
}

function TextEditor({
  entry,
  positions,
  open,
  onToggle,
}: {
  entry: PanelTextEntry;
  positions: string[];
  open: boolean;
  onToggle: () => void;
}) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState({
    value: entry.value || "",
    lang: entry.lang || "",
    banner_url: entry.banner_url || "",
    banner_position: entry.banner_position || "",
  });

  const invalidate = [["texts"]];
  const save = usePanelAction(panelTextsApi.saveText, { invalidate });
  const remove = usePanelAction(panelTextsApi.deleteText, { invalidate });

  const placeholders = Object.entries(entry.placeholders || {});

  return (
    <div className="rounded-md border border-border">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-2 px-3 py-2.5 text-right hover:bg-surface-2"
      >
        <ChevronDown size={16} className={`shrink-0 text-muted transition-transform ${open ? "rotate-180" : ""}`} />
        <span className="flex-1 text-sm font-medium text-text">{entry.title || entry.key}</span>
        <code className="ltr-field hidden text-[11px] text-muted sm:inline">{entry.key}</code>
        {entry.stored ? <Badge tone="success">{t("panel.texts.customised")}</Badge> : <Badge tone="muted">{t("panel.common.default")}</Badge>}
      </button>

      {open && (
        <div className="space-y-3 border-t border-border p-3">
          {placeholders.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-xs text-muted">{t("panel.texts.availableVariables")}:</span>
              {placeholders.map(([name, label]) => (
                <code
                  key={name}
                  title={label}
                  className="ltr-field rounded bg-surface-2 px-1.5 py-0.5 text-[11px] text-primary"
                >
                  {`{${name}}`}
                </code>
              ))}
            </div>
          )}

          <label className="block text-sm">
            <span className="mb-1.5 block text-muted">{t("panel.common.text")}</span>
            <textarea
              rows={5}
              value={draft.value}
              onChange={(event) => setDraft({ ...draft, value: event.target.value })}
              className="w-full rounded-md border border-border bg-surface p-3 text-text outline-none focus:border-primary focus:ring-4 focus:ring-primary/10"
            />
          </label>

          <div className="grid gap-3 sm:grid-cols-3">
            <Input
              label={t("panel.texts.bannerUrl")}
              ltr
              value={draft.banner_url}
              onChange={(event) => setDraft({ ...draft, banner_url: event.target.value })}
            />
            <SelectField
              label={t("panel.texts.bannerPosition")}
              options={positions.map((value) => ({ value, label: positionLabels(t)[value] || value }))}
              value={draft.banner_position}
              onChange={(event) => setDraft({ ...draft, banner_position: event.target.value })}
            />
            <Input
              label={t("panel.texts.language")}
              ltr
              maxLength={10}
              value={draft.lang}
              onChange={(event) => setDraft({ ...draft, lang: event.target.value })}
            />
          </div>

          <div className="flex flex-wrap justify-end gap-2">
            {entry.stored && (
              <ConfirmButton
                size="sm"
                variant="danger"
                message={t("panel.texts.resetConfirm")}
                onConfirm={() => remove.mutate({ key: entry.key, lang: draft.lang })}
              >
                {t("panel.common.restoreDefaults")}
              </ConfirmButton>
            )}
            <Button size="sm" loading={save.isPending} onClick={() => save.mutate({ key: entry.key, ...draft })}>
              {t("common.save")}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
