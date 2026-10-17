import { useEffect, useState } from "react";
import { Copy, Download, Send } from "lucide-react";
import { useTranslation } from "react-i18next";
import { panelWebappThemesApi } from "../../../../api/panel";
import { Button, Modal, Spinner } from "../../../../components/ui";
import { useToast } from "../../../../components/ui/Toast";
import { useWebAppAuth } from "../../../../hooks/useWebAppAuth";
import { copyToClipboard } from "../../../../lib/format";
import { usePanelAction } from "../../../../queries/usePanelApi";
import type { WebappThemeShareResponse } from "../../../../types/panel";
import { downloadPack } from "../shared";
import type { LibraryTheme } from "./shared";

export interface ShareThemeDialogProps {
  item: LibraryTheme | null;
  onClose: () => void;
}

/** Share a library theme with another admin: as code to paste, a file, or a file sent to their Telegram. */
export function ShareThemeDialog({ item, onClose }: ShareThemeDialogProps) {
  const { t } = useTranslation();
  const { auth } = useWebAppAuth();
  const toast = useToast();
  const send = usePanelAction(panelWebappThemesApi.sendTheme);
  const [share, setShare] = useState<WebappThemeShareResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const themeId = item?.entry?.id ?? null;
  const k = (key: string, options?: Record<string, unknown>) => t(`panel.webappThemes.share.${key}`, options);

  useEffect(() => {
    setShare(null);
    setError(null);
    if (themeId === null || !auth) return;
    let cancelled = false;
    panelWebappThemesApi
      .shareTheme({ ...auth, theme_id: themeId })
      .then((result) => !cancelled && setShare(result))
      .catch((exc: Error) => !cancelled && setError(exc.message || t("apiErrors.actionFailed")));
    return () => {
      cancelled = true;
    };
  }, [themeId, auth, t]);

  const code = share ? JSON.stringify(share.data, null, 2) : "";

  const copy = () =>
    void copyToClipboard(code)
      .then(() => toast.show(k("copied"), "success"))
      .catch(() => toast.show(k("copyFailed"), "error"));

  return (
    <Modal open={item !== null} onClose={onClose} title={k("title", { name: item?.name ?? "" })} size="lg">
      <div className="flex flex-col gap-3 pb-4">
        <p className="text-sm text-muted">{k("text")}</p>
        {error ? (
          <p className="rounded-sm bg-danger/10 px-3 py-2 text-xs text-danger">{error}</p>
        ) : !share ? (
          <div className="flex justify-center py-8">
            <Spinner />
          </div>
        ) : (
          <>
            <div className="grid gap-2 sm:grid-cols-3">
              <Button variant="secondary" onClick={copy}>
                <Copy size={15} />
                {k("copy")}
              </Button>
              <Button variant="secondary" onClick={() => downloadPack(share.data, share.file_name)}>
                <Download size={15} />
                {k("download")}
              </Button>
              <Button
                variant="secondary"
                loading={send.isPending}
                onClick={() => themeId !== null && send.mutate({ theme_id: themeId })}
              >
                <Send size={15} />
                {k("telegram")}
              </Button>
            </div>
            <textarea
              readOnly
              value={code}
              onFocus={(event) => event.target.select()}
              aria-label={k("code")}
              className="ltr-field h-48 w-full resize-y rounded-sm border border-border bg-surface-2 p-3 font-mono text-2xs text-text outline-none focus:border-primary"
            />
            <p className="text-2xs text-muted">{k("hint")}</p>
          </>
        )}
      </div>
    </Modal>
  );
}
