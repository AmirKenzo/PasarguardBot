import { useState } from "react";
import { Copy, Info, Pencil, Plus, Sparkles, Trash2, X as XIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button, EmptyState, Input } from "../../../components/ui";
import { useToast } from "../../../components/ui/Toast";
import { panelKeyboardApi } from "../../../api/panel";
import type { PanelKeyboardButton, PanelKeyboardResponse } from "../../../types/panel";
import { usePanelAction } from "../../../queries/usePanelApi";
import { ConfirmButton, SelectField } from "../components";
import { buttonLabel, INVALIDATE, sectionLabels, styleDraftOf } from "./shared";

/** The save endpoint rewrites text and colour too, so send the current values back unchanged. */
function iconSavePayload(button: PanelKeyboardButton, icon: string) {
  return { key: button.key, text: button.text || "", style: styleDraftOf(button), icon };
}

export function EmojiTab({ data }: { data: PanelKeyboardResponse }) {
  const { t } = useTranslation();
  const [adding, setAdding] = useState(false);
  const withIcon = data.buttons.filter((button) => button.icon != null);
  const withoutIcon = data.buttons.filter((button) => button.icon == null);

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3 rounded-xl border border-primary/25 bg-primary/5 p-3">
        <Info size={18} className="mt-0.5 shrink-0 text-primary" />
        <div className="min-w-0 space-y-1">
          <p className="text-sm font-semibold text-text">{t("panel.keyboard.premiumEmojiInfoTitle")}</p>
          <p className="text-xs leading-relaxed text-muted">{t("panel.keyboard.premiumEmojiInfo")}</p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 sm:gap-3">
        <Stat label={t("panel.keyboard.statWithIcon")} value={withIcon.length} tone="text-success" />
        <Stat label={t("panel.keyboard.statWithoutIcon")} value={withoutIcon.length} tone="text-muted" />
        <Stat label={t("panel.keyboard.statTotal")} value={data.buttons.length} tone="text-primary" />
      </div>

      <div className="rounded-xl border border-border bg-surface p-3 sm:p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold text-text">{t("panel.keyboard.iconsTitle")}</h2>
            <p className="mt-0.5 text-xs text-muted">{t("panel.keyboard.emojiIdHint")}</p>
          </div>
          {!adding && (
            <Button size="sm" variant="secondary" onClick={() => setAdding(true)} disabled={withoutIcon.length === 0}>
              <Plus size={14} />
              {t("panel.keyboard.addIcon")}
            </Button>
          )}
        </div>

        {adding && <AddIconForm candidates={withoutIcon} onDone={() => setAdding(false)} />}

        {withIcon.length === 0 ? (
          <EmptyState icon={Sparkles} title={t("panel.keyboard.noIconYet")} description={t("panel.keyboard.emojiIdHint")} />
        ) : (
          <div className="overflow-hidden rounded-lg border border-border">
            {withIcon.map((button) => (
              <IconRow key={button.key} button={button} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-3">
      <p className="truncate text-[11px] text-muted sm:text-xs">{label}</p>
      <p className={`mt-1 text-lg font-bold sm:text-xl ${tone}`}>{value}</p>
    </div>
  );
}

function IconRow({ button }: { button: PanelKeyboardButton }) {
  const { t } = useTranslation();
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(String(button.icon ?? ""));
  const save = usePanelAction(panelKeyboardApi.saveButton, { invalidate: INVALIDATE });
  const clear = usePanelAction(panelKeyboardApi.clearIcon, { invalidate: INVALIDATE });

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(String(button.icon));
      toast.show(t("panel.keyboard.copied"), "success");
    } catch {
      toast.show(String(button.icon), "info");
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2.5 border-b border-border px-3 py-2.5 last:border-0">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/12 text-primary">
        <Sparkles size={16} />
      </span>
      <div className="min-w-0 flex-1 basis-[calc(100%-3rem)] sm:basis-0">
        <p className="truncate text-sm font-medium text-text">{button.title || button.key}</p>
        <p className="truncate text-xs text-muted">
          {sectionLabels(t)[button.section] || button.section} · {buttonLabel(button)}
        </p>
      </div>
      {editing ? (
        <div className="flex w-full items-center gap-1.5 ps-[46px] sm:w-auto sm:ps-0">
          <Input dense ltr inputMode="numeric" value={value} onChange={(event) => setValue(event.target.value)} />
          <Button
            size="sm"
            loading={save.isPending}
            onClick={() => save.mutate(iconSavePayload(button, value.trim()), { onSuccess: () => setEditing(false) })}
          >
            {t("common.save")}
          </Button>
          <button
            type="button"
            aria-label={t("panel.common.dismiss")}
            onClick={() => setEditing(false)}
            className="rounded-md p-2 text-muted hover:bg-surface-2"
          >
            <XIcon size={14} />
          </button>
        </div>
      ) : (
        <div className="flex w-full items-center gap-1.5 ps-[46px] sm:w-auto sm:ps-0">
          <button
            type="button"
            onClick={() => void copy()}
            title={t("panel.keyboard.copyId")}
            className="ltr-field me-auto flex items-center gap-1.5 rounded-md bg-surface-2 px-2 py-1.5 font-mono text-[11px] text-muted hover:text-text"
          >
            {button.icon}
            <Copy size={12} />
          </button>
          <button
            type="button"
            aria-label={t("panel.keyboard.editIcon")}
            title={t("panel.keyboard.editIcon")}
            onClick={() => setEditing(true)}
            className="rounded-md border border-border p-1.5 text-muted hover:text-text"
          >
            <Pencil size={14} />
          </button>
          <ConfirmButton
            size="sm"
            variant="ghost"
            aria-label={t("panel.keyboard.clearIcon")}
            message={t("panel.keyboard.iconClearConfirm")}
            onConfirm={() => clear.mutate({ key: button.key })}
          >
            <Trash2 size={14} className="text-danger" />
          </ConfirmButton>
        </div>
      )}
    </div>
  );
}

function AddIconForm({ candidates, onDone }: { candidates: PanelKeyboardButton[]; onDone: () => void }) {
  const { t } = useTranslation();
  const [key, setKey] = useState(candidates[0]?.key ?? "");
  const [icon, setIcon] = useState("");
  const save = usePanelAction(panelKeyboardApi.saveButton, { invalidate: INVALIDATE });
  const labels = sectionLabels(t);
  const button = candidates.find((item) => item.key === key);

  return (
    <div className="mb-3 grid gap-3 rounded-lg border border-primary/30 bg-primary/5 p-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] sm:items-end">
      <SelectField
        label={t("panel.keyboard.button")}
        value={key}
        onChange={(event) => setKey(event.target.value)}
        options={candidates.map((item) => ({
          value: item.key,
          label: `${labels[item.section] || item.section} · ${item.title || item.key}`,
        }))}
      />
      <Input
        label={t("panel.keyboard.emojiId")}
        ltr
        inputMode="numeric"
        value={icon}
        onChange={(event) => setIcon(event.target.value)}
      />
      <div className="flex gap-2">
        <Button size="sm" variant="ghost" onClick={onDone}>
          {t("panel.common.dismiss")}
        </Button>
        <Button
          size="sm"
          loading={save.isPending}
          disabled={!button || !icon.trim()}
          onClick={() => button && save.mutate(iconSavePayload(button, icon.trim()), { onSuccess: onDone })}
        >
          {t("common.save")}
        </Button>
      </div>
    </div>
  );
}
