import { useEffect, useRef, useState } from "react";
import type { ChangeEvent } from "react";
import { FileUp } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button, Input, Modal } from "../../../../components/ui";
import { MAX_PACK_FILE_BYTES } from "../shared";
import { parseShareText } from "./shared";
import type { ParsedShare } from "./shared";
import { ThemeThumb } from "./ThemeThumb";

export interface ImportThemeDialogProps {
  open: boolean;
  onClose: () => void;
  onImport: (share: ParsedShare, activate: boolean) => void;
  saving: boolean;
}

/** Add a theme another admin shared: read the file or code, show it, then save it to the library. */
export function ImportThemeDialog({ open, onClose, onImport, saving }: ImportThemeDialogProps) {
  const { t } = useTranslation();
  const fileRef = useRef<HTMLInputElement>(null);
  const [pasted, setPasted] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [parsed, setParsed] = useState<ParsedShare | null>(null);
  const k = (key: string, options?: Record<string, unknown>) => t(`panel.webappThemes.import.${key}`, options);

  useEffect(() => {
    if (!open) return;
    setPasted("");
    setError(null);
    setParsed(null);
  }, [open]);

  const load = (text: string) => {
    try {
      const share = parseShareText(text);
      setParsed({ ...share, name: share.name || k("defaultName") });
      setError(null);
    } catch (exc) {
      setError(t((exc as Error).message));
    }
  };

  const pickFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (file.size > MAX_PACK_FILE_BYTES) {
      setError(t("panel.themePacks.errorTooLarge"));
      return;
    }
    load(await file.text());
  };

  return (
    <Modal open={open} onClose={onClose} title={k("title")}>
      <div className="flex flex-col gap-3 pb-4">
        {parsed ? (
          <>
            <div className="overflow-hidden rounded-md border border-border">
              <ThemeThumb theme={parsed.theme} />
            </div>
            <Input
              label={k("name")}
              value={parsed.name}
              maxLength={100}
              onChange={(event) => setParsed({ ...parsed, name: event.target.value })}
            />
            {parsed.sourceBot && <p className="text-xs text-muted">{k("from", { bot: parsed.sourceBot })}</p>}
            {parsed.filled > 0 && (
              <p className="rounded-sm bg-warning/10 px-3 py-2 text-xs text-warning">
                {k("filled", { count: parsed.filled })}
              </p>
            )}
            <div className="grid grid-cols-2 gap-2">
              <Button variant="secondary" loading={saving} onClick={() => onImport(parsed, false)}>
                {k("add")}
              </Button>
              <Button loading={saving} onClick={() => onImport(parsed, true)}>
                {k("addActivate")}
              </Button>
            </div>
            <Button variant="ghost" size="sm" onClick={() => setParsed(null)}>
              {k("back")}
            </Button>
          </>
        ) : (
          <>
            <input
              ref={fileRef}
              type="file"
              accept=".json,application/json,text/plain"
              className="hidden"
              onChange={pickFile}
            />
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              className="flex flex-col items-center gap-2 rounded-md border-2 border-dashed border-border px-4 py-6 text-sm text-muted transition-colors hover:border-primary/50 hover:text-text"
            >
              <FileUp size={26} />
              {k("pickFile")}
            </button>
            <p className="text-center text-xs text-muted">{t("panel.themePacks.orPaste")}</p>
            <textarea
              value={pasted}
              onChange={(event) => setPasted(event.target.value)}
              placeholder='{"format": "kenzo-theme-pack", "webapp": {...}}'
              aria-label={k("code")}
              className="ltr-field h-28 w-full resize-y rounded-sm border border-border bg-surface-2 p-3 font-mono text-xs text-text outline-none focus:border-primary"
            />
            {error && <p className="rounded-sm bg-danger/10 px-3 py-2 text-xs text-danger">{error}</p>}
            <Button size="sm" disabled={!pasted.trim()} onClick={() => load(pasted)}>
              {t("panel.themePacks.continue")}
            </Button>
          </>
        )}
      </div>
    </Modal>
  );
}
