import { useEffect, useRef, useState } from "react";
import type { ChangeEvent } from "react";
import { FileUp } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button, Modal } from "../../../components/ui";
import type { ThemePackData } from "../../../types/panel";
import { MAX_PACK_FILE_BYTES, parsePackText } from "./shared";

export interface ImportDialogProps {
  open: boolean;
  onClose: () => void;
  onLoaded: (pack: ThemePackData) => void;
}

export function ImportDialog({ open, onClose, onLoaded }: ImportDialogProps) {
  const { t } = useTranslation();
  const fileRef = useRef<HTMLInputElement>(null);
  const [pasted, setPasted] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setPasted("");
    setError(null);
  }, [open]);

  const load = (text: string) => {
    try {
      onLoaded(parsePackText(text));
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
    <Modal open={open} onClose={onClose} title={t("panel.themePacks.importTitle")}>
      <div className="flex flex-col gap-3 pb-4">
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
          className="flex flex-col items-center gap-2 rounded-xl border-2 border-dashed border-border px-4 py-6 text-sm text-muted transition-colors hover:border-primary/50 hover:text-text"
        >
          <FileUp size={26} />
          {t("panel.themePacks.pickFile")}
        </button>
        <p className="text-center text-xs text-muted">{t("panel.themePacks.orPaste")}</p>
        <textarea
          value={pasted}
          onChange={(event) => setPasted(event.target.value)}
          placeholder='{"format": "kenzo-theme-pack", ...}'
          className="ltr-field h-28 w-full resize-y rounded-xl border border-border bg-surface-2 p-3 font-mono text-xs text-text outline-none focus:border-primary"
        />
        {error && <p className="rounded-lg bg-danger/10 px-3 py-2 text-xs text-danger">{error}</p>}
        <Button size="sm" disabled={!pasted.trim()} onClick={() => load(pasted)}>
          {t("panel.themePacks.continue")}
        </Button>
      </div>
    </Modal>
  );
}
