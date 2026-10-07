import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import type { LucideIcon } from "lucide-react";
import {
  ArrowRight,
  Bold,
  Check,
  Code,
  EyeOff,
  ImageOff,
  Info,
  Italic,
  Link2,
  Plus,
  Quote,
  RotateCcw,
  Sparkles,
  Strikethrough,
  Undo2,
  X as XIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "../../../components/ui";
import { useToast } from "../../../components/ui/Toast";
import type { PanelTextEntry } from "../../../types/panel";

// Telegram's limit for a plain message.
export const MAX_MESSAGE_LENGTH = 4096;
const VARIABLES_COLLAPSED = 6;

/** Markers of the bot's markdown dialect (telethon markdown plus the custom delimiters in app/__init__.py). */
const FORMATS: ({ key: string; icon: LucideIcon; before: string; after: string } | null)[] = [
  { key: "bold", icon: Bold, before: "**", after: "**" },
  { key: "italic", icon: Italic, before: "__", after: "__" },
  { key: "strike", icon: Strikethrough, before: "~~", after: "~~" },
  { key: "code", icon: Code, before: "`", after: "`" },
  null,
  { key: "spoiler", icon: EyeOff, before: "^sp^", after: "^sp^" },
  { key: "quote", icon: Quote, before: "^q^", after: "^q^" },
  null,
  { key: "link", icon: Link2, before: "[", after: "](https://)" },
];

/** Accepts a raw custom emoji id or a tg://emoji?id= link. */
function parseEmojiId(raw: string): string | null {
  const value = raw.trim();
  const id = (value.match(/id=(\d+)/) || value.match(/^(\d+)$/) || [])[1];
  return id && id.length >= 5 ? id : null;
}

export function canSaveText(value: string, stored: string): boolean {
  return value !== stored && value.trim().length > 0 && value.length <= MAX_MESSAGE_LENGTH;
}

interface TextEditorProps {
  entry: PanelTextEntry;
  value: string;
  saving: boolean;
  onChange: (value: string) => void;
  onSave: () => void;
  onBack: () => void;
  onRequestReset: () => void;
}

export function TextEditor({ entry, value, saving, onChange, onSave, onBack, onRequestReset }: TextEditorProps) {
  const { t } = useTranslation();
  const toast = useToast();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  // Last caret position in the textarea. Toolbar buttons and the emoji box take focus
  // away, so insertions use this instead of the live selection.
  const caretRef = useRef<[number, number] | null>(null);
  const [variablesOpen, setVariablesOpen] = useState(false);
  const [emojiOpen, setEmojiOpen] = useState(false);
  const [emojiDraft, setEmojiDraft] = useState("");
  const [emojiError, setEmojiError] = useState(false);
  const emojiInputRef = useRef<HTMLInputElement>(null);

  const stored = entry.value || "";
  const dirty = value !== stored;
  const overLimit = value.length > MAX_MESSAGE_LENGTH;
  const canSave = canSaveText(value, stored);

  useEffect(() => {
    const onSelectionChange = () => {
      const textarea = textareaRef.current;
      if (textarea && document.activeElement === textarea) {
        caretRef.current = [textarea.selectionStart, textarea.selectionEnd];
      }
    };
    document.addEventListener("selectionchange", onSelectionChange);
    return () => document.removeEventListener("selectionchange", onSelectionChange);
  }, []);

  useEffect(() => {
    if (emojiOpen) emojiInputRef.current?.focus();
  }, [emojiOpen]);

  function trackCaret() {
    const textarea = textareaRef.current;
    if (textarea) caretRef.current = [textarea.selectionStart, textarea.selectionEnd];
  }

  /** Inserts at the remembered caret, or at the end when the user never clicked in the text. */
  function insert(before: string, after = "") {
    const length = value.length;
    const [start, end] = caretRef.current
      ? [Math.min(caretRef.current[0], length), Math.min(caretRef.current[1], length)]
      : [length, length];
    onChange(value.slice(0, start) + before + value.slice(start, end) + after + value.slice(end));
    const caret = start + before.length + (end - start);
    caretRef.current = [caret, caret];
    requestAnimationFrame(() => {
      textareaRef.current?.focus();
      textareaRef.current?.setSelectionRange(caret, caret);
    });
  }

  function closeEmoji() {
    setEmojiOpen(false);
    setEmojiDraft("");
    setEmojiError(false);
  }

  function addEmoji() {
    const id = parseEmojiId(emojiDraft);
    if (!id) {
      setEmojiError(true);
      emojiInputRef.current?.focus();
      return;
    }
    insert(`[⭐](emoji/${id})`);
    closeEmoji();
    toast.show(t("panel.texts.emojiAdded"), "success");
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      if (canSave) onSave();
    }
  }

  const placeholders = Object.entries(entry.placeholders || {});
  const shownPlaceholders = variablesOpen ? placeholders : placeholders.slice(0, VARIABLES_COLLAPSED);
  const hiddenCount = placeholders.length - VARIABLES_COLLAPSED;

  const badge = dirty
    ? { label: t("panel.texts.unsaved"), cls: "bg-warning/12 text-warning" }
    : entry.stored
      ? { label: t("panel.texts.statusSet"), cls: "bg-success/12 text-success" }
      : { label: t("panel.texts.statusUnset"), cls: "bg-surface-2 text-muted" };

  return (
    <div className="flex flex-col rounded-2xl border border-border bg-surface lg:max-h-[calc(100vh-2rem)] lg:overflow-hidden">
      <div className="sticky top-[calc(4.25rem+env(safe-area-inset-top,0px))] z-10 md:top-0 flex shrink-0 items-center gap-2.5 rounded-t-2xl border-b border-border bg-surface px-3.5 py-3 lg:static">
        <button
          type="button"
          onClick={onBack}
          aria-label={t("panel.texts.back")}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-surface-2 text-text lg:hidden"
        >
          <ArrowRight size={18} />
        </button>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[15px] font-bold text-text">{entry.title || entry.key}</p>
          <code className="ltr-field block truncate text-[11px] text-muted" style={{ textAlign: "right" }}>
            {entry.key}
          </code>
        </div>
        <span className={`shrink-0 whitespace-nowrap rounded-full px-2.5 py-1 text-[11px] font-semibold ${badge.cls}`}>
          {badge.label}
        </span>
      </div>

      <div
        role="toolbar"
        aria-label={t("panel.texts.toolbar")}
        className="flex shrink-0 flex-wrap items-center gap-0.5 border-b border-border px-2 py-1.5"
      >
        {FORMATS.map((format, index) => {
          if (!format) return <span key={`sep-${index}`} className="mx-1 h-5 w-px shrink-0 bg-border" />;
          const Icon = format.icon;
          const label = t(`panel.texts.fmt.${format.key}`);
          return (
            <button
              key={format.key}
              type="button"
              title={label}
              aria-label={label}
              onClick={() => insert(format.before, format.after)}
              className="flex h-[38px] min-w-[38px] shrink-0 items-center justify-center rounded-lg text-muted transition-colors hover:bg-surface-2 hover:text-text"
            >
              <Icon size={16} />
            </button>
          );
        })}
        <button
          type="button"
          aria-expanded={emojiOpen}
          onClick={() => (emojiOpen ? closeEmoji() : setEmojiOpen(true))}
          className={`ms-auto flex h-[38px] shrink-0 items-center gap-1.5 rounded-lg border px-3 text-xs font-semibold transition-colors ${
            emojiOpen ? "border-transparent bg-warning/12 text-warning" : "border-border bg-surface-2 text-text hover:border-warning/40"
          }`}
        >
          <Sparkles size={16} className="text-warning" />
          {t("panel.texts.fmt.emoji")}
        </button>
      </div>

      {emojiOpen && (
        <div className="flex shrink-0 flex-col gap-2 border-b border-border bg-surface-2/60 px-3.5 py-3">
          <p className="text-xs leading-relaxed text-muted">
            {t("panel.texts.emojiHint")}{" "}
            <code className="ltr-field rounded bg-surface px-1.5 text-[11px]">tg://emoji?id=…</code>
          </p>
          <div className="flex gap-2">
            <input
              ref={emojiInputRef}
              inputMode="numeric"
              autoComplete="off"
              aria-label={t("panel.texts.emojiIdLabel")}
              placeholder="5368324170671202286"
              value={emojiDraft}
              onChange={(event) => {
                setEmojiDraft(event.target.value);
                setEmojiError(false);
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  addEmoji();
                } else if (event.key === "Escape") {
                  closeEmoji();
                }
              }}
              className={`ltr-field h-10 min-w-0 flex-1 rounded-lg border bg-surface px-3 font-mono text-sm outline-none focus:ring-4 ${
                emojiError ? "border-danger focus:ring-danger/10" : "border-border focus:border-primary focus:ring-primary/10"
              }`}
            />
            <Button size="sm" onClick={addEmoji}>
              <Plus size={14} />
              {t("panel.texts.emojiAdd")}
            </Button>
            <button
              type="button"
              aria-label={t("panel.texts.cancel")}
              onClick={closeEmoji}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-muted hover:bg-surface hover:text-text"
            >
              <XIcon size={16} />
            </button>
          </div>
          {emojiError && <p className="text-xs text-danger">{t("panel.texts.emojiInvalid")}</p>}
        </div>
      )}

      <div className="flex min-h-0 flex-1 flex-col gap-3 p-3.5 lg:overflow-y-auto lg:overscroll-contain">
        {placeholders.length > 0 && (
          <div>
            <p className="mb-1.5 text-xs text-muted">{t("panel.texts.variablesHint")}</p>
            <div className="flex flex-wrap gap-1.5">
              {shownPlaceholders.map(([name, label]) => (
                <button
                  key={name}
                  type="button"
                  onClick={() => insert(`{${name}}`)}
                  className="flex items-center gap-1.5 rounded-lg bg-primary/12 px-2.5 py-1.5 text-xs text-primary transition-transform active:scale-95"
                >
                  {label}
                  <code className="ltr-field text-[10.5px] opacity-70">{`{${name}}`}</code>
                </button>
              ))}
              {hiddenCount > 0 && (
                <button
                  type="button"
                  onClick={() => setVariablesOpen(!variablesOpen)}
                  className="rounded-lg border border-dashed border-border px-2.5 py-1.5 text-xs text-muted hover:text-text"
                >
                  {variablesOpen ? t("panel.texts.showLess") : t("panel.texts.moreVariables", { count: hiddenCount })}
                </button>
              )}
            </div>
          </div>
        )}

        <div>
          <textarea
            ref={textareaRef}
            value={value}
            aria-label={t("panel.common.text")}
            placeholder={entry.stored ? "" : t("panel.texts.unsetPlaceholder")}
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={handleKeyDown}
            onBlur={trackCaret}
            onSelect={trackCaret}
            onKeyUp={trackCaret}
            onMouseUp={trackCaret}
            onTouchEnd={() => setTimeout(trackCaret)}
            className={`min-h-[46vh] w-full resize-y rounded-xl border bg-surface-2 px-3.5 py-3 text-sm leading-[1.9] text-text outline-none transition-colors focus:bg-surface focus:ring-4 lg:min-h-[200px] ${
              overLimit ? "border-danger ring-4 ring-danger/10" : "border-border focus:border-primary focus:ring-primary/10"
            }`}
          />
          <div className="mt-1.5 flex justify-between gap-2.5 text-[11.5px] text-muted">
            <span>{t("panel.texts.formatHint")}</span>
            <span className={`ltr-field shrink-0 tabular-nums ${overLimit ? "font-bold text-danger" : ""}`}>
              {value.length.toLocaleString("en")} / {MAX_MESSAGE_LENGTH.toLocaleString("en")}
            </span>
          </div>
        </div>

        {dirty && !value.trim() && (
          <p className="flex items-start gap-2 rounded-lg bg-warning/12 px-2.5 py-2 text-xs text-warning">
            <Info size={14} className="mt-0.5 shrink-0" />
            {t("panel.texts.emptyValue")}
          </p>
        )}

        <div className="flex items-center gap-2.5 rounded-xl border border-dashed border-border px-3 py-2.5 text-[12.5px] text-muted">
          <ImageOff size={16} className="shrink-0" />
          <span className="font-semibold text-text">{t("panel.texts.banner")}</span>
          <span>{t("panel.texts.bannerDisabled")}</span>
          <span className="ms-auto whitespace-nowrap rounded-full bg-surface-2 px-2.5 py-0.5 text-[11px]">
            {t("panel.texts.disabled")}
          </span>
        </div>
      </div>

      <div className="safe-area-pb sticky bottom-0 z-10 flex shrink-0 items-center justify-between gap-2 rounded-b-2xl border-t border-border bg-surface px-3.5 py-2.5 shadow-[0_-8px_20px_rgba(0,0,0,0.08)] lg:static lg:shadow-none">
        <div className="flex flex-wrap gap-1.5">
          {entry.stored && (
            <Button size="sm" variant="ghost" className="text-danger hover:bg-danger/10" onClick={onRequestReset}>
              <RotateCcw size={14} />
              {t("panel.texts.removeSet")}
            </Button>
          )}
          {dirty && (
            <Button size="sm" variant="ghost" onClick={() => onChange(stored)}>
              <Undo2 size={14} />
              <span className="hidden sm:inline">{t("panel.texts.discard")}</span>
            </Button>
          )}
        </div>
        <Button size="sm" loading={saving} disabled={!canSave} onClick={onSave}>
          <Check size={14} />
          {t("common.save")}
          <kbd className="ltr-field hidden rounded border border-current px-1 font-mono text-[10px] opacity-70 lg:inline">
            Ctrl+S
          </kbd>
        </Button>
      </div>
    </div>
  );
}
