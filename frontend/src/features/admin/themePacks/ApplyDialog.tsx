import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { panelThemePacksApi } from "../../../api/panel";
import { Button, ErrorState, Modal, Skeleton } from "../../../components/ui";
import type {
  ThemePackApplyMode,
  ThemePackData,
  ThemePackItem,
  ThemePackPreviewResponse,
  ThemePackSource,
} from "../../../types/panel";
import { usePanelAction } from "../../../queries/usePanelApi";
import { PreviewList } from "./PreviewList";
import { INVALIDATE_ALL, isApplicable } from "./shared";

export interface ApplyDialogProps {
  open: boolean;
  title: string;
  source: ThemePackSource;
  /** A pack read from a file can also be kept in the library. */
  onSaveToLibrary?: (pack: ThemePackData) => void;
  savePending?: boolean;
  onClose: () => void;
}

/** Preview a pack against the bot, pick what to take, choose merge or replace, and apply. */
export function ApplyDialog({ open, title, source, onSaveToLibrary, savePending, onClose }: ApplyDialogProps) {
  const { t } = useTranslation();
  const preview = usePanelAction(panelThemePacksApi.previewPack);
  const apply = usePanelAction(panelThemePacksApi.applyPack, { invalidate: INVALIDATE_ALL });
  const [result, setResult] = useState<ThemePackPreviewResponse | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [mode, setMode] = useState<ThemePackApplyMode>("merge");
  const { mutate: runPreview } = preview;

  useEffect(() => {
    if (!open) return;
    setResult(null);
    setMode("merge");
    runPreview(source, {
      onSuccess: (data) => {
        setResult(data);
        setSelected(new Set(data.items.filter(isApplicable).map((item) => item.id)));
      },
    });
  }, [open, source, runPreview]);

  const items = useMemo<ThemePackItem[]>(() => result?.items ?? [], [result]);
  const applicable = items.filter(isApplicable);
  const select = (filter: (item: ThemePackItem) => boolean) =>
    setSelected(new Set(applicable.filter(filter).map((item) => item.id)));

  const submit = () =>
    apply.mutate({ ...source, item_ids: [...selected], mode }, { onSuccess: () => onClose() });

  return (
    <Modal open={open} onClose={onClose} title={title} size="lg">
      {preview.isPending || (!result && !preview.isError) ? (
        <div className="flex flex-col gap-2 pb-4">
          <Skeleton className="h-10" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
      ) : preview.isError || !result ? (
        <div className="pb-4">
          <ErrorState message={preview.error?.message ?? t("apiErrors.actionFailed")} onRetry={() => runPreview(source)} />
        </div>
      ) : (
        <div className="flex flex-col gap-3 pb-1">
          {result.source.bot && (
            <p className="text-xs text-muted">
              {t("panel.themePacks.madeOn", { bot: result.source.bot, version: result.source.app_version || "?" })}
            </p>
          )}
          <div className="flex flex-wrap gap-1.5 text-xs">
            <span className="text-muted">{t("panel.themePacks.quickSelect")}</span>
            <button type="button" className="text-primary" onClick={() => select(() => true)}>
              {t("panel.themePacks.selectAll")}
            </button>
            <span className="text-muted">·</span>
            <button type="button" className="text-primary" onClick={() => select((item) => item.status === "new")}>
              {t("panel.themePacks.selectNew")}
            </button>
            <span className="text-muted">·</span>
            <button type="button" className="text-primary" onClick={() => select(() => false)}>
              {t("panel.themePacks.selectNone")}
            </button>
          </div>

          <PreviewList items={items} selected={selected} onChange={setSelected} />

          <fieldset className="rounded-xl border border-border p-3">
            <legend className="px-1 text-sm font-semibold text-text">{t("panel.themePacks.modeTitle")}</legend>
            {(["merge", "replace"] as const).map((value) => (
              <label key={value} className="flex cursor-pointer items-start gap-2.5 py-1.5">
                <input
                  type="radio"
                  name="theme-pack-mode"
                  className="mt-1 accent-primary"
                  checked={mode === value}
                  onChange={() => setMode(value)}
                />
                <span>
                  <span className="block text-sm text-text">{t(`panel.themePacks.mode.${value}`)}</span>
                  <span className="block text-xs text-muted">{t(`panel.themePacks.mode.${value}Hint`)}</span>
                </span>
              </label>
            ))}
          </fieldset>

          <p className="text-xs text-muted">{t("panel.themePacks.undoNote")}</p>

          <div className="sticky bottom-0 -mx-5 flex flex-wrap justify-end gap-2 border-t border-border bg-surface px-5 py-3">
            {onSaveToLibrary && source.pack && (
              <Button variant="secondary" size="sm" loading={savePending} onClick={() => onSaveToLibrary(source.pack!)}>
                {t("panel.themePacks.saveToLibrary")}
              </Button>
            )}
            <Button
              size="sm"
              loading={apply.isPending}
              disabled={selected.size === 0 && mode === "merge"}
              onClick={submit}
            >
              {t("panel.themePacks.applySelected", { count: selected.size })}
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
