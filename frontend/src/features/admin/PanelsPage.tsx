import { useState } from "react";
import { Plus } from "lucide-react";
import { useTranslation } from "react-i18next";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button, ErrorState, Skeleton } from "../../components/ui";
import { panelPanelsApi } from "../../api/panel";
import { usePanelQuery } from "../../queries/usePanelApi";
import { SectionCard } from "./components";
import { PanelCard } from "./panels/PanelCard";
import { PanelQuickEditModal, EMPTY_PANEL_DRAFT } from "./panels/PanelQuickEditModal";
import type { PanelDraft } from "./panels/PanelQuickEditModal";
import { PanelInfoModal } from "./panels/PanelInfoModal";
import { PanelSettingsModal } from "./panels/PanelSettingsModal";

export default function AdminPanelsPage() {
  const { t } = useTranslation();
  const [draft, setDraft] = useState<PanelDraft | null>(null);
  const [infoCode, setInfoCode] = useState<number | null>(null);
  const [settingsCode, setSettingsCode] = useState<number | null>(null);

  const query = usePanelQuery(["panels"], (auth) => panelPanelsApi.listPanels(auth));
  const panels = query.data?.panels || [];
  const activePanel = panels.find((p) => p.code === (infoCode ?? settingsCode));

  return (
    <>
      <PageHeader
        title={t("panel.common.panels")}
        subtitle={t("panel.panels.subtitle")}
        action={
          <Button size="sm" onClick={() => setDraft({ ...EMPTY_PANEL_DRAFT })}>
            <Plus size={16} />
            {t("panel.common.addPanel")}
          </Button>
        }
      />

      {query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : (
        <SectionCard title={t("panel.panels.title")}>
          {query.isLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : panels.length === 0 ? (
            <div className="py-10 text-center">
              <p className="font-semibold text-text">{t("panel.panels.empty")}</p>
              <p className="mt-1 text-sm text-muted">{t("panel.panels.addFirst")}</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {panels.map((panel) => (
                <PanelCard
                  key={panel.code}
                  panel={panel}
                  trialEnabled={panel.test_enabled}
                  onView={() => setInfoCode(panel.code)}
                  onEdit={() =>
                    setDraft({
                      code: panel.code,
                      name: panel.name,
                      base_url: panel.base_url,
                      tunnel_url: panel.tunnel_url || "",
                      auth_type: panel.auth_type,
                      username: panel.username || "",
                      secret: "",
                      enable: panel.enable,
                      test_enabled: panel.test_enabled,
                      test_volume_gb: panel.test_volume_gb,
                      test_duration_days: panel.test_duration_days,
                    })
                  }
                  onSettings={() => setSettingsCode(panel.code)}
                />
              ))}
            </div>
          )}
        </SectionCard>
      )}

      <PanelQuickEditModal draft={draft} onClose={() => setDraft(null)} onChange={setDraft} />
      <PanelInfoModal code={infoCode} name={activePanel?.name} onClose={() => setInfoCode(null)} />
      <PanelSettingsModal code={settingsCode} name={activePanel?.name} onClose={() => setSettingsCode(null)} />
    </>
  );
}
