import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Check, ChevronDown, RotateCcw, Search, Sparkles } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Badge, Button, EmptyState, Input } from "../../../components/ui";
import { panelKeyboardApi } from "../../../api/panel";
import type { PanelKeyboardButton, PanelKeyboardResponse } from "../../../types/panel";
import { usePanelAction } from "../../../queries/usePanelApi";
import {
  blockedLabels,
  ButtonChip,
  buttonLabel,
  INVALIDATE,
  isCustomized,
  renderedStyle,
  sectionLabels,
  styleDraftOf,
  styleLabels,
  SWATCH_CLASSES,
} from "./shared";

const ALL = "all";

interface ButtonsTabProps {
  data: PanelKeyboardResponse;
  /** Button to open and scroll to, e.g. after "edit" in the layout tab. */
  focusKey: string | null;
  onFocusHandled: () => void;
}

export function ButtonsTab({ data, focusKey, onFocusHandled }: ButtonsTabProps) {
  const { t } = useTranslation();
  const [section, setSection] = useState<string>(ALL);
  const [query, setQuery] = useState("");
  const [openKey, setOpenKey] = useState<string | null>(null);

  const sections = data.sections.filter((slug) => data.buttons.some((button) => button.section === slug));
  const labels = sectionLabels(t);

  useEffect(() => {
    if (!focusKey) return;
    setSection(ALL);
    setQuery("");
    setOpenKey(focusKey);
    onFocusHandled();
    requestAnimationFrame(() =>
      document.getElementById(`kb-btn-${focusKey}`)?.scrollIntoView({ behavior: "smooth", block: "center" })
    );
  }, [focusKey, onFocusHandled]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return data.buttons.filter((button) => {
      if (section !== ALL && button.section !== section) return false;
      if (!needle) return true;
      return [button.key, button.title, button.text, button.default_text].some((value) =>
        (value || "").toLowerCase().includes(needle)
      );
    });
  }, [data.buttons, query, section]);

  const grouped = sections
    .map((slug) => ({ slug, buttons: filtered.filter((button) => button.section === slug) }))
    .filter((group) => group.buttons.length > 0);

  return (
    <div className="rounded-xl border border-border bg-surface p-3 sm:p-4">
      <div className="mb-3">
        <Input
          placeholder={t("panel.keyboard.searchButtons")}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          suffix={<Search size={15} className="text-muted" />}
        />
      </div>
      <div className="no-scrollbar -mx-3 mb-3 flex gap-1.5 overflow-x-auto px-3 sm:mx-0 sm:flex-wrap sm:px-0">
        {[ALL, ...sections].map((slug) => {
          const count =
            slug === ALL ? data.buttons.length : data.buttons.filter((button) => button.section === slug).length;
          const active = section === slug;
          return (
            <button
              key={slug}
              type="button"
              onClick={() => setSection(slug)}
              className={`flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                active ? "border-primary/40 bg-primary/15 text-primary" : "border-border text-muted hover:text-text"
              }`}
            >
              {slug === ALL ? t("panel.keyboard.allSections") : labels[slug] || slug}
              <span className="opacity-60">{count}</span>
            </button>
          );
        })}
      </div>

      {grouped.length === 0 ? (
        <EmptyState title={t("panel.keyboard.noResults")} />
      ) : (
        <div className="space-y-4">
          {grouped.map((group) => (
            <div key={group.slug}>
              {section === ALL && (
                <p className="mb-1.5 px-1 text-xs font-semibold text-muted">{labels[group.slug] || group.slug}</p>
              )}
              <div className="overflow-hidden rounded-lg border border-border">
                {group.buttons.map((button) => (
                  <ButtonRow
                    key={button.key}
                    button={button}
                    styles={data.style_options}
                    glassMode={data.glass_mode}
                    open={openKey === button.key}
                    onToggle={() => setOpenKey(openKey === button.key ? null : button.key)}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ButtonRow({
  button,
  styles,
  glassMode,
  open,
  onToggle,
}: {
  button: PanelKeyboardButton;
  styles: string[];
  glassMode: boolean;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <div id={`kb-btn-${button.key}`} className="border-b border-border last:border-0">
      <button
        type="button"
        onClick={onToggle}
        className={`flex w-full items-center gap-2.5 px-3 py-2.5 text-start transition-colors hover:bg-surface-2 ${
          open ? "bg-surface-2" : ""
        }`}
      >
        <ButtonChip
          label={buttonLabel(button)}
          style={renderedStyle(button, glassMode)}
          icon={button.icon != null}
          className="max-w-[55%] shrink-0 sm:max-w-[260px]"
        />
        <div className="hidden min-w-0 flex-1 sm:block">
          <p className="truncate text-xs text-muted">{button.title}</p>
          <code className="ltr-field block truncate text-[11px] text-muted/70">{button.key}</code>
        </div>
        <div className="ms-auto flex shrink-0 items-center gap-1.5">
          {button.blocked ? <AlertTriangle size={14} className="text-warning" /> : null}
          {isCustomized(button) ? <span className="h-1.5 w-1.5 rounded-full bg-primary" /> : null}
          <ChevronDown size={16} className={`text-muted transition-transform ${open ? "rotate-180" : ""}`} />
        </div>
      </button>
      {open && <ButtonEditor button={button} styles={styles} glassMode={glassMode} onSaved={onToggle} />}
    </div>
  );
}

function ButtonEditor({
  button,
  styles,
  glassMode,
  onSaved,
}: {
  button: PanelKeyboardButton;
  styles: string[];
  glassMode: boolean;
  onSaved: () => void;
}) {
  const { t } = useTranslation();
  const defaultIcon = button.default_icon != null ? String(button.default_icon) : "";
  const [draft, setDraft] = useState({
    text: button.text || "",
    style: styleDraftOf(button),
    icon: button.icon != null ? String(button.icon) : defaultIcon,
  });
  const save = usePanelAction(panelKeyboardApi.saveButton, { invalidate: INVALIDATE });
  const labelsByStyle = styleLabels(t);
  const previewLabel = draft.text.trim() || button.default_text || button.title || button.key;

  return (
    <div className="space-y-4 border-t border-border bg-surface-2/40 p-3 sm:p-4">
      {button.blocked && (
        <p className="flex items-start gap-1.5 rounded-md bg-warning/10 px-3 py-2 text-xs text-warning">
          <AlertTriangle size={13} className="mt-0.5 shrink-0" />
          {blockedLabels(t)[button.blocked] || button.blocked}
        </p>
      )}

      <div className="flex flex-col items-center gap-1.5 rounded-lg border border-dashed border-border p-4">
        <span className="text-[11px] text-muted">{t("panel.keyboard.livePreview")}</span>
        <ButtonChip
          label={previewLabel}
          style={renderedStyle(button, glassMode, draft.style)}
          icon={Boolean(draft.icon.trim())}
          className="max-w-full px-4 py-2 text-sm"
        />
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <Input
          label={t("panel.common.buttonText")}
          placeholder={button.default_text || ""}
          value={draft.text}
          maxLength={100}
          onChange={(event) => setDraft({ ...draft, text: event.target.value })}
        />
        <Input
          label={t("panel.common.premiumEmojiId")}
          ltr
          inputMode="numeric"
          placeholder={t("panel.keyboard.emptyMeansNoIcon")}
          value={draft.icon}
          onChange={(event) => setDraft({ ...draft, icon: event.target.value })}
        />
      </div>

      <div>
        <span className="mb-1.5 block text-sm text-muted">{t("panel.keyboard.colour")}</span>
        <div className="flex flex-wrap gap-2">
          {styles.map((value) => {
            const active = draft.style === value;
            return (
              <button
                key={value || "default"}
                type="button"
                onClick={() => setDraft({ ...draft, style: value })}
                className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1.5 text-xs font-medium transition-colors ${
                  active ? "border-primary/50 bg-primary/10 text-text" : "border-border text-muted hover:text-text"
                }`}
              >
                <span className={`h-3.5 w-3.5 rounded-full ${SWATCH_CLASSES[value] ?? SWATCH_CLASSES.none}`} />
                {labelsByStyle[value] || value}
                {active && <Check size={12} className="text-primary" />}
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <code className="ltr-field rounded bg-surface px-2 py-1 text-[11px] text-muted">{button.key}</code>
          {button.in_home && <Badge tone="primary">{t("panel.keyboard.mainMenu")}</Badge>}
          {button.icon != null && (
            <Badge tone="success">
              <Sparkles size={11} />
              {t("panel.keyboard.icon")}
            </Badge>
          )}
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setDraft({ text: "", style: "", icon: defaultIcon })}
            title={t("panel.keyboard.resetButtonHint")}
          >
            <RotateCcw size={14} />
            {t("panel.keyboard.resetButton")}
          </Button>
          <Button size="sm" loading={save.isPending} onClick={() => save.mutate({ key: button.key, ...draft }, { onSuccess: onSaved })}>
            <Check size={14} />
            {t("common.save")}
          </Button>
        </div>
      </div>
    </div>
  );
}
