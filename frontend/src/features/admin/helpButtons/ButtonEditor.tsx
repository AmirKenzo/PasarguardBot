import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { keepPreviousData } from "@tanstack/react-query";
import {
  AlertTriangle,
  Archive,
  CheckCircle2,
  Check,
  FileBox,
  Info,
  Plus,
  RefreshCw,
  Trash2,
  X as XIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Input, Spinner } from "../../../components/ui";
import { panelHelpButtonsApi } from "../../../api/panel";
import type { HelpButtonKind, PanelHelpButton, PanelHelpTarget } from "../../../types/panel";
import { usePanelAction, usePanelQuery } from "../../../queries/usePanelApi";
import { ConfirmButton } from "../components";
import { ButtonChip, Hint } from "../keyboard/shared";
import { chipStyle, ColourPicker, HELP_INVALIDATE, KIND_ICONS, styleDraft, TEXTAREA_CLASS } from "./shared";

interface Draft {
  text: string;
  style: string;
  icon: string;
  url: string;
  repo: string;
  ios_url: string;
  custom_message: string;
  targets: PanelHelpTarget[];
}

const newTargetId = () => `n${Math.random().toString(16).slice(2, 9)}`;

function draftOf(button: PanelHelpButton | null): Draft {
  return {
    text: button?.text || "",
    style: styleDraft(button?.style),
    icon: button?.icon != null ? String(button.icon) : "",
    url: button?.url || "",
    repo: button?.repo || "",
    ios_url: button?.ios_url || "",
    custom_message: button?.custom_message || "",
    targets: (button?.targets || []).map((target) => ({ ...target, patterns: [...target.patterns] })),
  };
}

/** Debounces a value so typing a pattern doesn't fire a request per key press. */
function useDebounced<T>(value: T, delay = 450): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

interface ButtonEditorProps {
  /** Existing button, or null with `kind` set to create one. */
  button: PanelHelpButton | null;
  kind: HelpButtonKind;
  onSaved: (id: number | null) => void;
  onDeleted: () => void;
  onClose: () => void;
}

export function ButtonEditor({ button, kind, onSaved, onDeleted, onClose }: ButtonEditorProps) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState<Draft>(() => draftOf(button));
  const save = usePanelAction(panelHelpButtonsApi.saveButton, { invalidate: HELP_INVALIDATE });
  const remove = usePanelAction(panelHelpButtonsApi.deleteButton, { invalidate: HELP_INVALIDATE });
  const Icon = KIND_ICONS[kind];
  const patch = (next: Partial<Draft>) => setDraft((current) => ({ ...current, ...next }));

  const submit = () =>
    save.mutate(
      { id: button?.id ?? null, kind, ...draft, targets: kind === "app" ? draft.targets : [] },
      { onSuccess: (result) => onSaved(result.id ?? button?.id ?? null) }
    );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-text">
          <Icon size={16} className="text-primary" />
          {button ? t(`panel.helpButtons.kind.${kind}`) : t(`panel.helpButtons.newKind.${kind}`)}
        </h2>
        <button
          type="button"
          onClick={onClose}
          aria-label={t("common.close")}
          className="flex h-8 w-8 items-center justify-center rounded-md text-muted hover:bg-surface-2 hover:text-text"
        >
          <XIcon size={16} />
        </button>
      </div>

      <div className="flex justify-center rounded-lg border border-dashed border-border p-3">
        <ButtonChip
          label={draft.text.trim() || t("panel.helpButtons.untitled")}
          style={chipStyle(draft.style)}
          icon={Boolean(draft.icon.trim())}
          className="max-w-full px-4 py-2 text-sm"
        />
      </div>

      <Input
        label={t("panel.common.buttonText")}
        value={draft.text}
        maxLength={64}
        onChange={(event) => patch({ text: event.target.value })}
      />

      <div>
        <span className="mb-1.5 block text-sm text-muted">{t("panel.keyboard.colour")}</span>
        <ColourPicker value={draft.style} onChange={(style) => patch({ style })} />
      </div>

      <Input
        label={t("panel.common.premiumEmojiId")}
        ltr
        inputMode="numeric"
        placeholder={t("panel.keyboard.emptyMeansNoIcon")}
        value={draft.icon}
        onChange={(event) => patch({ icon: event.target.value })}
      />

      {kind === "link" && (
        <Input
          label={t("panel.helpButtons.url")}
          ltr
          placeholder="https://t.me/your_channel"
          value={draft.url}
          maxLength={500}
          onChange={(event) => patch({ url: event.target.value })}
        />
      )}

      {kind === "text" && (
        <label className="block text-sm">
          <span className="mb-1.5 block text-muted">{t("panel.helpButtons.customMessage")}</span>
          <textarea
            rows={5}
            maxLength={4000}
            value={draft.custom_message}
            onChange={(event) => patch({ custom_message: event.target.value })}
            className={TEXTAREA_CLASS}
          />
          <span className="mt-1 block text-xs text-muted">{t("panel.helpButtons.customMessageHint")}</span>
        </label>
      )}

      {kind === "app" && (
        <AppFields button={button} draft={draft} onChange={patch} />
      )}

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3">
        {button ? (
          <ConfirmButton
            size="sm"
            variant="ghost"
            message={t("panel.helpButtons.deleteConfirm", { name: button.text })}
            loading={remove.isPending}
            onConfirm={() => remove.mutate({ id: button.id }, { onSuccess: onDeleted })}
          >
            <Trash2 size={14} className="text-danger" />
            {t("common.delete")}
          </ConfirmButton>
        ) : (
          <span />
        )}
        <div className="flex gap-2">
          <Button size="sm" variant="ghost" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button size="sm" loading={save.isPending} onClick={submit}>
            <Check size={14} />
            {t("common.save")}
          </Button>
        </div>
      </div>
    </div>
  );
}

function AppFields({
  button,
  draft,
  onChange,
}: {
  button: PanelHelpButton | null;
  draft: Draft;
  onChange: (next: Partial<Draft>) => void;
}) {
  const { t } = useTranslation();
  const setTarget = (index: number, next: Partial<PanelHelpTarget>) =>
    onChange({ targets: draft.targets.map((target, i) => (i === index ? { ...target, ...next } : target)) });

  return (
    <div className="space-y-4">
      {button?.legacy_categories && (
        <p className="flex items-start gap-1.5 rounded-md bg-primary/10 px-3 py-2 text-xs text-primary">
          <Info size={13} className="mt-0.5 shrink-0" />
          {t("panel.helpButtons.legacyCategories")}
        </p>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <Input
          label={t("panel.helpButtons.repo")}
          ltr
          placeholder="2dust/v2rayNG"
          value={draft.repo}
          maxLength={241}
          onChange={(event) => onChange({ repo: event.target.value })}
        />
        <Input
          label={t("panel.helpButtons.iosUrl")}
          ltr
          placeholder="https://apps.apple.com/…"
          value={draft.ios_url}
          maxLength={500}
          onChange={(event) => onChange({ ios_url: event.target.value })}
        />
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm text-muted">{t("panel.helpButtons.targets")}</span>
          <Button
            size="sm"
            variant="secondary"
            onClick={() =>
              onChange({
                targets: [...draft.targets, { id: newTargetId(), button_text: "", button_style: null, patterns: [] }],
              })
            }
          >
            <Plus size={14} />
            {t("panel.helpButtons.addTarget")}
          </Button>
        </div>
        <Hint>{t("panel.helpButtons.patternsHint")}</Hint>
      </div>

      <ReleaseMatcher repo={draft.repo} targets={draft.targets}>
        {(matches) =>
          draft.targets.map((target, index) => (
            <div key={target.id} className="space-y-2 rounded-md border border-border p-3">
              <div className="flex items-end gap-2">
                <Input
                  dense
                  label={t("panel.helpButtons.targetText")}
                  value={target.button_text}
                  maxLength={64}
                  onChange={(event) => setTarget(index, { button_text: event.target.value })}
                />
                <button
                  type="button"
                  aria-label={t("common.delete")}
                  onClick={() => onChange({ targets: draft.targets.filter((_, i) => i !== index) })}
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-border text-danger hover:bg-danger/10"
                >
                  <Trash2 size={14} />
                </button>
              </div>
              <ColourPicker
                value={styleDraft(target.button_style)}
                onChange={(style) => setTarget(index, { button_style: style === "none" ? null : style })}
              />
              <Input
                dense
                ltr
                label={t("panel.common.premiumEmojiId")}
                placeholder={t("panel.keyboard.emptyMeansNoIcon")}
                value={target.button_icon || ""}
                onChange={(event) => setTarget(index, { button_icon: event.target.value || null })}
              />
              <label className="block text-sm">
                <span className="mb-1.5 block text-muted">{t("panel.helpButtons.patterns")}</span>
                <textarea
                  rows={Math.max(2, target.patterns.length + 1)}
                  dir="ltr"
                  spellCheck={false}
                  placeholder={"v2rayNG_%.%.%_universal.apk"}
                  value={target.patterns.join("\n")}
                  onChange={(event) => setTarget(index, { patterns: event.target.value.split("\n") })}
                  className={`${TEXTAREA_CLASS} font-mono text-xs`}
                />
              </label>
              <MatchBadge count={matches?.[target.id]} />
            </div>
          ))
        }
      </ReleaseMatcher>

      {button && <StoredVersions appId={button.id} />}
    </div>
  );
}

function MatchBadge({ count }: { count: number | undefined }) {
  const { t } = useTranslation();
  if (count === undefined) return null;
  return count > 0 ? (
    <p className="flex items-center gap-1 text-xs text-success">
      <CheckCircle2 size={13} />
      {t("panel.helpButtons.matchCount", { count })}
    </p>
  ) : (
    <p className="flex items-center gap-1 text-xs text-warning">
      <AlertTriangle size={13} />
      {t("panel.helpButtons.noMatch")}
    </p>
  );
}

const REPO_RE = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;

/**
 * Asks the server which latest-release files each target's patterns pick, so the
 * result is exactly what the bot will send, and lists every file with its owner.
 */
function ReleaseMatcher({
  repo,
  targets,
  children,
}: {
  repo: string;
  targets: PanelHelpTarget[];
  children: (matches: Record<string, number> | undefined) => ReactNode;
}) {
  const { t } = useTranslation();
  const [refresh, setRefresh] = useState(0);
  const cleanRepo = repo.trim().replace(/^https:\/\/github\.com\//, "").replace(/\/+$/, "");
  const request = useMemo(
    () => ({
      repo: cleanRepo,
      targets: targets.map((target) => ({ ...target, patterns: target.patterns.filter((p) => p.trim()) })),
    }),
    [cleanRepo, targets]
  );
  const debounced = useDebounced(request);
  const valid = REPO_RE.test(debounced.repo);
  const query = usePanelQuery(
    ["help-release", debounced, refresh],
    (auth) => panelHelpButtonsApi.releaseFiles({ ...auth, ...debounced, refresh: refresh > 0 }),
    { enabled: valid, placeholderData: keepPreviousData, retry: false, staleTime: 60_000 }
  );
  const data = valid ? query.data : undefined;
  const names = new Map(targets.map((target) => [target.id, target.button_text || "—"]));

  return (
    <>
      {children(data?.matches)}
      <div className="rounded-md border border-border bg-surface-2/40 p-3">
        <div className="mb-2 flex items-center justify-between gap-2">
          <span className="flex items-center gap-1.5 text-xs font-medium text-text">
            <FileBox size={14} />
            {t("panel.helpButtons.releaseFiles")}
            {data?.tag && <Badge tone="primary">{data.tag}</Badge>}
            {query.isFetching && <Spinner size={12} />}
          </span>
          <button
            type="button"
            disabled={!valid}
            onClick={() => setRefresh((n) => n + 1)}
            title={t("panel.helpButtons.refreshRelease")}
            aria-label={t("panel.helpButtons.refreshRelease")}
            className="flex h-7 w-7 items-center justify-center rounded-md text-muted hover:bg-surface-2 hover:text-text disabled:opacity-40"
          >
            <RefreshCw size={13} />
          </button>
        </div>
        {!valid ? (
          <Hint>{t("panel.helpButtons.enterRepo")}</Hint>
        ) : query.isError ? (
          <p className="text-xs text-danger">{query.error.message}</p>
        ) : !data ? (
          <Hint>{t("common.loading")}</Hint>
        ) : data.files.length === 0 ? (
          <Hint>{t("panel.helpButtons.noReleaseFiles")}</Hint>
        ) : (
          <div className="divide-y divide-border">
            {data.files.map((file) => (
              <div key={file.name} className="flex items-center justify-between gap-2 py-1.5 text-xs">
                <span className="ltr-field truncate font-mono text-text">{file.name}</span>
                <span className="flex shrink-0 items-center gap-2">
                  <span className="text-muted">{file.size_mb} MB</span>
                  {file.target_id ? (
                    <Badge tone="success">{names.get(file.target_id) || file.target_id}</Badge>
                  ) : (
                    <span className="text-muted">—</span>
                  )}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}

function StoredVersions({ appId }: { appId: number }) {
  const { t } = useTranslation();
  const query = usePanelQuery(["help-versions", appId], (auth) => panelHelpButtonsApi.getVersions({ ...auth, id: appId }));
  const remove = usePanelAction(panelHelpButtonsApi.deleteVersion, { invalidate: [["help-versions", appId]] });
  const versions = query.data?.versions || [];

  return (
    <div className="rounded-md border border-border p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-xs font-medium text-text">
          <Archive size={14} />
          {t("panel.helpButtons.storedVersions")}
        </span>
        {versions.length > 0 && (
          <ConfirmButton
            size="sm"
            variant="ghost"
            message={t("panel.helpButtons.deleteAllVersionsConfirm")}
            onConfirm={() => remove.mutate({ id: appId, tag: "" })}
          >
            <Trash2 size={13} className="text-danger" />
            {t("panel.helpButtons.deleteAllVersions")}
          </ConfirmButton>
        )}
      </div>
      {query.isLoading ? (
        <Hint>{t("common.loading")}</Hint>
      ) : versions.length === 0 ? (
        <Hint>{t("panel.helpButtons.noStoredVersions")}</Hint>
      ) : (
        <div className="divide-y divide-border">
          {versions.map((version) => (
            <div key={version.tag} className="flex items-center justify-between gap-2 py-1.5 text-xs">
              <span className="min-w-0">
                <span className="ltr-field font-medium text-text">{version.tag}</span>
                <span className="ms-2 text-muted">{t("panel.helpButtons.fileCount", { count: version.count })}</span>
              </span>
              <ConfirmButton
                size="sm"
                variant="ghost"
                message={t("panel.helpButtons.deleteVersionConfirm", { tag: version.tag })}
                onConfirm={() => remove.mutate({ id: appId, tag: version.tag })}
              >
                <Trash2 size={13} className="text-danger" />
              </ConfirmButton>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
