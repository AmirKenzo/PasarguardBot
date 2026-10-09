import { useEffect, useRef, useState } from "react";
import { Check, Copy } from "lucide-react";
import { useTranslation } from "react-i18next";
import { copyToClipboard } from "../../lib/format";
import { useTelegram } from "../../hooks/useTelegram";

export interface CopyFieldProps {
  label: string;
  value: string;
  /** Text shown instead of `value` (e.g. a masked or shortened form). */
  display?: string;
  mono?: boolean;
  onCopied?: () => void;
}

/** Read-only value row with a copy button that briefly turns green after copying. */
export function CopyField({ label, value, display, mono = true, onCopied }: CopyFieldProps) {
  const { t } = useTranslation();
  const { haptic } = useTelegram();
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const copy = () => {
    void copyToClipboard(value)
      .then(() => {
        haptic.notify("success");
        setCopied(true);
        onCopied?.();
        window.clearTimeout(timer.current);
        timer.current = window.setTimeout(() => setCopied(false), 1800);
      })
      .catch(() => haptic.notify("error"));
  };

  return (
    <button
      type="button"
      onClick={copy}
      className={`flex w-full items-center gap-3 rounded-md border px-3 py-2.5 text-start transition-colors ${
        copied ? "border-success/40 bg-success/7" : "border-border bg-bg hover:border-primary/30"
      }`}
    >
      <div className="min-w-0 flex-1">
        <p className="text-[10.5px] text-muted">{copied ? `${label} · ${t("ui.copied")}` : label}</p>
        <p className={`truncate text-[13px] font-semibold text-text ${mono ? "font-mono" : ""}`}>
          <bdi dir="ltr">{display ?? value}</bdi>
        </p>
      </div>
      <span
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-sm ${
          copied ? "bg-success/15 text-success" : "bg-primary/12 text-primary"
        }`}
      >
        {copied ? <Check size={15} /> : <Copy size={15} />}
      </span>
    </button>
  );
}
