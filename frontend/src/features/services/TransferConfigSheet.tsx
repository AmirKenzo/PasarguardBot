import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Sheet } from "../../components/ui/Sheet";
import { Button, Input } from "../../components/ui";
import { useTelegram } from "../../hooks/useTelegram";
import { useTransferConfigMutation } from "../../queries/useServices";

export interface TransferConfigSheetProps {
  open: boolean;
  onClose: () => void;
  code: number;
  username: string;
}

export function TransferConfigSheet({ open, onClose, code, username }: TransferConfigSheetProps) {
  const { t } = useTranslation();
  const { haptic } = useTelegram();
  const transfer = useTransferConfigMutation();
  const [targetId, setTargetId] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  const handleClose = () => {
    setTargetId("");
    setError("");
    setDone(false);
    transfer.reset();
    onClose();
  };

  const handleSubmit = () => {
    const value = targetId.trim();
    if (!/^\d+$/.test(value)) {
      setError(t("transferConfig.invalidId"));
      return;
    }
    setError("");
    haptic.impact("medium");
    transfer.mutate(
      { code, targetUserId: Number(value) },
      {
        onSuccess: () => {
          haptic.notify("success");
          setDone(true);
        },
        onError: (err) => setError((err as Error).message),
      }
    );
  };

  return (
    <Sheet open={open} onClose={handleClose} title={t("transferConfig.title")}>
      <p className="mb-4 text-xs text-muted">{username}</p>
      {done ? (
        <div className="space-y-4">
          <p className="rounded-md border border-success/25 bg-success/10 px-4 py-3 text-sm text-success">
            {t("transferConfig.success")}
          </p>
          <Button type="button" fullWidth onClick={handleClose}>
            {t("ui.close")}
          </Button>
        </div>
      ) : (
        <div className="space-y-4">
          <p className="text-sm text-muted">{t("transferConfig.hint")}</p>
          <Input
            inputMode="numeric"
            value={targetId}
            onChange={(e) => setTargetId(e.target.value.replace(/\D/g, ""))}
            placeholder={t("transferConfig.targetIdPlaceholder")}
            ltr
          />
          {error && <p className="text-sm text-danger">{error}</p>}
          <Button type="button" fullWidth loading={transfer.isPending} onClick={handleSubmit}>
            {t("transferConfig.confirm")}
          </Button>
        </div>
      )}
    </Sheet>
  );
}
