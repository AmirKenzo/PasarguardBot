import { Check } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button, Input } from "../../../components/ui";
import { SegmentedControl } from "../../../components/ui/Select";
import { FormModal, Toggle } from "../components";
import { panelPanelsApi } from "../../../api/panel";
import type { PanelSaveRequest } from "../../../types/panel";
import { usePanelAction } from "../../../queries/usePanelApi";

export type PanelDraft = Omit<PanelSaveRequest, "session_token" | "init_data">;

export const EMPTY_PANEL_DRAFT: PanelDraft = {
  code: null,
  name: "",
  base_url: "",
  tunnel_url: "",
  auth_type: "password",
  username: "",
  secret: "",
  enable: true,
  test_enabled: false,
  test_volume_gb: 2,
  test_duration_days: 3,
};

export interface PanelQuickEditModalProps {
  draft: PanelDraft | null;
  onClose: () => void;
  onChange: (draft: PanelDraft) => void;
}

export function PanelQuickEditModal({ draft, onClose, onChange }: PanelQuickEditModalProps) {
  const { t } = useTranslation();
  const save = usePanelAction(panelPanelsApi.savePanel, {
    invalidate: [["panels"], ["plans"], ["dashboard"]],
  });

  return (
    <FormModal
      open={draft !== null}
      onClose={onClose}
      title={draft?.code ? t("panel.panels.editTitle", { name: draft.name }) : t("panel.common.addPanel")}
    >
      {draft && (
        <div className="space-y-3">
          <Input
            label={t("panel.panels.panelName")}
            value={draft.name}
            onChange={(event) => onChange({ ...draft, name: event.target.value })}
          />
          <p className="-mt-2 text-xs text-muted">{t("panel.panels.nameEmojiHint")}</p>

          <label className="block w-full text-sm">
            <span className="mb-1.5 block text-muted">{t("panel.panels.authType")}</span>
            <SegmentedControl
              options={[
                { value: "api_key", label: "API Key" },
                { value: "password", label: t("panel.panels.usernamePassword") },
              ]}
              value={draft.auth_type || "password"}
              onChange={(auth_type) => onChange({ ...draft, auth_type })}
            />
          </label>

          {draft.auth_type === "password" && (
            <Input
              label={t("panel.panels.panelUsername")}
              ltr
              value={draft.username || ""}
              onChange={(event) => onChange({ ...draft, username: event.target.value })}
            />
          )}
          <Input
            label={draft.auth_type === "api_key" ? "API Key" : t("panel.panels.password")}
            type="password"
            ltr
            autoComplete="new-password"
            placeholder={draft.code ? t("panel.panels.changeHint") : ""}
            value={draft.secret || ""}
            onChange={(event) => onChange({ ...draft, secret: event.target.value })}
          />
          <Input
            label={t("panel.panels.url")}
            ltr
            placeholder="https://panel.example.com"
            value={draft.base_url}
            onChange={(event) => onChange({ ...draft, base_url: event.target.value })}
          />
          <Input
            label={t("panel.panels.tunnelUrl")}
            ltr
            value={draft.tunnel_url || ""}
            onChange={(event) => onChange({ ...draft, tunnel_url: event.target.value })}
          />
          <Toggle
            checked={draft.enable ?? true}
            onChange={(enable) => onChange({ ...draft, enable })}
            label={t("panel.panels.enabled")}
            hint={t("panel.panels.enabledHint")}
          />
          <p className="text-xs text-muted">{t("panel.panels.verifyNote")}</p>
          <div className="flex justify-end gap-2 pt-1">
            <Button size="sm" variant="ghost" onClick={onClose}>
              {t("panel.common.dismiss")}
            </Button>
            <Button
              size="sm"
              loading={save.isPending}
              disabled={!draft.name.trim() || !draft.base_url.trim()}
              onClick={() => save.mutate(draft, { onSuccess: () => onClose() })}
            >
              <Check size={16} />
              {t("common.save")}
            </Button>
          </div>
        </div>
      )}
    </FormModal>
  );
}
