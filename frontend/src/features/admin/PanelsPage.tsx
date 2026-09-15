import { useState } from "react";
import { Plus } from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge, Button, ErrorState, Input, Skeleton } from "../../components/ui";
import { panelPanelsApi } from "../../api/panel";
import type { PanelRow, PanelSaveRequest } from "../../types/panel";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { ConfirmButton, DataTable, FormModal, SectionCard, SelectField, Toggle } from "./components";
import type { Column } from "./components";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

const authLabels = (t: TFunction): Record<string, string> => ({
  password: t("panel.panels.usernamePassword"),
  api_key: "API Key",
});

type Draft = Omit<PanelSaveRequest, "session_token" | "init_data">;

const EMPTY_DRAFT: Draft = {
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

export default function AdminPanelsPage() {
  const { t } = useTranslation();
  const [draft, setDraft] = useState<Draft | null>(null);

  const query = usePanelQuery(["panels"], (auth) => panelPanelsApi.listPanels(auth));
  const invalidate = [["panels"], ["plans"], ["dashboard"]];
  const save = usePanelAction(panelPanelsApi.savePanel, { invalidate });
  const test = usePanelAction(panelPanelsApi.testPanel);
  const remove = usePanelAction(panelPanelsApi.deletePanel, { invalidate });

  const authOptions = (query.data?.auth_types || ["password", "api_key"]).map((value) => ({
    value,
    label: authLabels(t)[value] || value,
  }));

  const columns: Column<PanelRow>[] = [
    { key: "code", header: t("panel.common.code"), cell: (row) => <code className="ltr-field text-xs">{row.code}</code> },
    { key: "name", header: t("panel.panels.name"), cell: (row) => row.name },
    {
      key: "url",
      header: t("panel.common.address"),
      secondary: true,
      cell: (row) => <span className="ltr-field break-all text-xs text-muted">{row.base_url}</span>,
    },
    {
      key: "auth",
      header: t("panel.panels.auth"),
      secondary: true,
      cell: (row) => <span className="text-xs">{authLabels(t)[row.auth_type] || row.auth_type}</span>,
    },
    {
      key: "status",
      header: t("panel.common.status"),
      cell: (row) => (row.enable ? <Badge tone="success">{t("panel.common.active")}</Badge> : <Badge tone="muted">{t("panel.common.inactive")}</Badge>),
    },
    {
      key: "actions",
      header: t("panel.common.actions"),
      cell: (row) => (
        <div className="flex flex-wrap gap-1.5">
          <Button size="sm" variant="ghost" loading={test.isPending} onClick={() => test.mutate({ code: row.code })}>
            {t("panel.panels.testConnection")}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() =>
              setDraft({
                code: row.code,
                name: row.name,
                base_url: row.base_url,
                tunnel_url: row.tunnel_url || "",
                auth_type: row.auth_type,
                username: row.username || "",
                secret: "",
                enable: row.enable,
                test_enabled: row.test_enabled,
                test_volume_gb: row.test_volume_gb,
                test_duration_days: row.test_duration_days,
              })
            }
          >
            {t("common.edit")}
          </Button>
          <ConfirmButton
            size="sm"
            variant="danger"
            message={t("panel.panels.deleteConfirm")}
            onConfirm={() => remove.mutate({ code: row.code })}
          >
            {t("common.delete")}
          </ConfirmButton>
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title={t("panel.common.panels")}
        subtitle={t("panel.panels.subtitle")}
        action={
          <Button size="sm" onClick={() => setDraft({ ...EMPTY_DRAFT })}>
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
          ) : (
            <DataTable
              columns={columns}
              rows={query.data?.panels || []}
              rowKey={(row) => row.code}
              emptyTitle={t("panel.panels.empty")}
              emptyDescription={t("panel.panels.addFirst")}
            />
          )}
        </SectionCard>
      )}

      <FormModal
        open={draft !== null}
        onClose={() => setDraft(null)}
        title={draft?.code ? t("panel.panels.editTitle", { name: draft.name }) : t("panel.common.addPanel")}
      >
        {draft && (
          <div className="space-y-3">
            <Input
              label={t("panel.panels.panelName")}
              value={draft.name}
              onChange={(event) => setDraft({ ...draft, name: event.target.value })}
            />
            <Input
              label={t("panel.panels.url")}
              ltr
              placeholder="https://panel.example.com"
              value={draft.base_url}
              onChange={(event) => setDraft({ ...draft, base_url: event.target.value })}
            />
            <Input
              label={t("panel.panels.tunnelUrl")}
              ltr
              value={draft.tunnel_url || ""}
              onChange={(event) => setDraft({ ...draft, tunnel_url: event.target.value })}
            />
            <SelectField
              label={t("panel.panels.authType")}
              options={authOptions}
              value={draft.auth_type}
              onChange={(event) => setDraft({ ...draft, auth_type: event.target.value })}
            />
            {draft.auth_type === "password" && (
              <Input
                label={t("panel.panels.panelUsername")}
                ltr
                value={draft.username || ""}
                onChange={(event) => setDraft({ ...draft, username: event.target.value })}
              />
            )}
            <Input
              label={draft.auth_type === "api_key" ? "API Key" : t("panel.panels.password")}
              type="password"
              ltr
              autoComplete="new-password"
              placeholder={draft.code ? t("panel.panels.changeHint") : ""}
              value={draft.secret || ""}
              onChange={(event) => setDraft({ ...draft, secret: event.target.value })}
            />
            <div className="space-y-3 rounded-md border border-border p-3">
              <Toggle
                checked={draft.test_enabled ?? false}
                onChange={(test_enabled) => setDraft({ ...draft, test_enabled })}
                label={t("panel.panels.trialEnabled")}
              />
              <p className="text-xs text-muted">{t("panel.panels.trialHint")}</p>
              {draft.test_enabled && (
                <div className="grid gap-3 sm:grid-cols-2">
                  <Input
                    label={t("panel.plans.volumeGb")}
                    inputMode="decimal"
                    value={String(draft.test_volume_gb ?? "")}
                    onChange={(event) => setDraft({ ...draft, test_volume_gb: Number(event.target.value) })}
                  />
                  <Input
                    label={t("panel.common.periodDays")}
                    inputMode="numeric"
                    value={String(draft.test_duration_days ?? "")}
                    onChange={(event) => setDraft({ ...draft, test_duration_days: Number(event.target.value) })}
                  />
                </div>
              )}
            </div>
            <Toggle
              checked={draft.enable ?? true}
              onChange={(enable) => setDraft({ ...draft, enable })}
              label={t("panel.panels.enabled")}
            />
            <p className="text-xs text-muted">
              {t("panel.panels.verifyNote")}
            </p>
            <div className="flex justify-end gap-2">
              <Button size="sm" variant="ghost" onClick={() => setDraft(null)}>
                {t("panel.common.dismiss")}
              </Button>
              <Button
                size="sm"
                loading={save.isPending}
                disabled={!draft.name.trim() || !draft.base_url.trim()}
                onClick={() => save.mutate(draft, { onSuccess: () => setDraft(null) })}
              >
                {t("common.save")}
              </Button>
            </div>
          </div>
        )}
      </FormModal>
    </>
  );
}
