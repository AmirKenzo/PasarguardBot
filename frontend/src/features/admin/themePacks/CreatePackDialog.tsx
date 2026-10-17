import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { panelThemePacksApi } from "../../../api/panel";
import { Button, Input, Modal } from "../../../components/ui";
import type { ThemePackOverviewResponse } from "../../../types/panel";
import { usePanelAction } from "../../../queries/usePanelApi";
import { KeySelector } from "./KeySelector";
import { ToggleRow } from "./ToggleRow";
import { THEME_PACKS_QUERY_KEY } from "./shared";

export interface CreatePackDialogProps {
  open: boolean;
  overview: ThemePackOverviewResponse;
  onClose: () => void;
  onCreated: (packId: number) => void;
}

export function CreatePackDialog({ open, overview, onClose, onCreated }: CreatePackDialogProps) {
  const { t } = useTranslation();
  const create = usePanelAction(panelThemePacksApi.createFromCurrent, { invalidate: [THEME_PACKS_QUERY_KEY] });
  const [name, setName] = useState("");
  const [textKeys, setTextKeys] = useState<Set<string>>(new Set());
  const [buttonKeys, setButtonKeys] = useState<Set<string>>(new Set());
  const [includeLayout, setIncludeLayout] = useState(false);
  const [includeBanners, setIncludeBanners] = useState(true);
  const [includeIcons, setIncludeIcons] = useState(true);
  const [includeDefaults, setIncludeDefaults] = useState(false);

  // Start from everything the admin customized; that is what people usually want to share.
  useEffect(() => {
    if (!open) return;
    setName("");
    setTextKeys(new Set(overview.texts.filter((entry) => entry.langs.length > 0).map((entry) => entry.key)));
    setButtonKeys(new Set(overview.buttons.filter((entry) => entry.customized).map((entry) => entry.key)));
    setIncludeLayout(overview.layout_customized);
  }, [open, overview]);

  const empty = textKeys.size === 0 && buttonKeys.size === 0 && !includeLayout;
  const submit = () =>
    create.mutate(
      {
        name: name.trim() || t("panel.themePacks.defaultName"),
        text_keys: [...textKeys],
        button_keys: [...buttonKeys],
        include_layout: includeLayout,
        include_banners: includeBanners,
        include_icons: includeIcons,
        include_defaults: includeDefaults,
      },
      {
        onSuccess: (result) => {
          if (result.pack_id) onCreated(result.pack_id);
        },
      }
    );

  return (
    <Modal open={open} onClose={onClose} title={t("panel.themePacks.createTitle")} size="lg">
      <div className="flex flex-col gap-4 pb-1">
        <Input
          label={t("panel.themePacks.name")}
          value={name}
          maxLength={100}
          placeholder={t("panel.themePacks.namePlaceholder")}
          onChange={(event) => setName(event.target.value)}
        />
        <KeySelector
          overview={overview}
          textKeys={textKeys}
          buttonKeys={buttonKeys}
          onTextKeys={setTextKeys}
          onButtonKeys={setButtonKeys}
        />
        <div className="flex flex-col gap-3 rounded-xl border border-border p-3">
          <ToggleRow checked={includeLayout} onChange={setIncludeLayout} label={t("panel.themePacks.includeLayout")} />
          <ToggleRow checked={includeBanners} onChange={setIncludeBanners} label={t("panel.themePacks.includeBanners")} />
          <ToggleRow checked={includeIcons} onChange={setIncludeIcons} label={t("panel.themePacks.includeIcons")} />
          <ToggleRow checked={includeDefaults} onChange={setIncludeDefaults} label={t("panel.themePacks.includeDefaults")} />
        </div>
        <p className="text-xs text-muted">{t("panel.themePacks.privacyNote")}</p>
        <div className="sticky bottom-0 -mx-5 flex justify-end gap-2 border-t border-border bg-surface px-5 py-3">
          <Button variant="ghost" size="sm" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button size="sm" loading={create.isPending} disabled={empty} onClick={submit}>
            {t("panel.themePacks.create")}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
