import { useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowDownWideNarrow,
  ArrowUpWideNarrow,
  Check,
  Clock,
  Filter,
  HardDrive,
  Pencil,
  Plus,
  Server,
  SlidersHorizontal,
  Trash2,
} from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge, Button, ErrorState, IconBadge, Input, Pagination, Skeleton } from "../../components/ui";
import { formatToman } from "../../lib/format";
import { panelPanelsApi, panelPlansApi } from "../../api/panel";
import type { PanelPlanRow, PanelPlanSaveRequest } from "../../types/panel";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { ConfirmButton, FormModal, IconMenuButton, MenuHeader, MenuRow, SectionCard, Toggle } from "./components";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

const planTypeLabels = (t: TFunction): Record<string, string> => ({
  volume: t("panel.plans.volumeBased"),
  fair_usage: t("panel.plans.fairUse"),
});

const resetLabels = (t: TFunction): Record<string, string> => ({
  no_reset: t("resetStrategy.no_reset"),
  day: t("resetStrategy.day"),
  week: t("resetStrategy.week"),
  month: t("resetStrategy.month"),
  year: t("resetStrategy.year"),
});

const styleLabels = (t: TFunction): Record<string, string> => ({
  "": t("panel.common.default"),
  primary: t("panel.common.blue"),
  success: t("panel.common.green"),
  danger: t("panel.common.red"),
});

const STYLE_SWATCH_CLASSES: Record<string, string> = {
  "": "bg-surface-2 border-border",
  primary: "bg-primary border-primary",
  success: "bg-success border-success",
  danger: "bg-danger border-danger",
};

const STYLE_PREVIEW_CLASSES: Record<string, string> = {
  "": "bg-surface-2 text-text border-border",
  primary: "bg-primary/15 text-primary border-primary/30",
  success: "bg-success/15 text-success border-success/30",
  danger: "bg-danger/15 text-danger border-danger/30",
};

const SORT_OPTIONS = (t: TFunction) => [
  { value: "newest", label: t("panel.plans.sortNewest"), icon: Clock },
  { value: "oldest", label: t("panel.plans.sortOldest"), icon: Clock },
  { value: "price_asc", label: t("panel.plans.sortPriceAsc"), icon: ArrowUpWideNarrow },
  { value: "price_desc", label: t("panel.plans.sortPriceDesc"), icon: ArrowDownWideNarrow },
  { value: "volume_asc", label: t("panel.plans.sortVolumeAsc"), icon: ArrowUpWideNarrow },
  { value: "volume_desc", label: t("panel.plans.sortVolumeDesc"), icon: ArrowDownWideNarrow },
  { value: "duration_asc", label: t("panel.plans.sortDurationAsc"), icon: ArrowUpWideNarrow },
  { value: "duration_desc", label: t("panel.plans.sortDurationDesc"), icon: ArrowDownWideNarrow },
];

const PAGE_SIZE = 10;

type Draft = Omit<PanelPlanSaveRequest, "session_token" | "init_data">;

const EMPTY_DRAFT: Draft = {
  plan_id: null,
  panel_code: 0,
  storage: 0,
  duration: 30,
  price: 0,
  plan_type: "volume",
  data_limit_reset_strategy: "no_reset",
  ip_limit: 0,
  display_button_text: "",
  button_style: "",
  button_icon: "",
};

export default function AdminPlansPage() {
  const { t } = useTranslation();
  const [panelFilter, setPanelFilter] = useState("");
  const [sort, setSort] = useState("newest");
  const [page, setPage] = useState(1);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [customButton, setCustomButton] = useState(false);

  const panelsQuery = usePanelQuery(["panel-options", "code,name"], (auth) =>
    panelPanelsApi.listPanelOptions({ ...auth, fields: ["code", "name"], limit: 100 })
  );
  const panels = panelsQuery.data?.panels || [];
  const panelOptions = panels.map((panel) => ({ value: String(panel.code), label: panel.name || `#${panel.code}` }));

  const query = usePanelQuery(["plans", panelFilter, sort, page], (auth) =>
    panelPlansApi.listPlans({ ...auth, panel: panelFilter, sort, page, limit: PAGE_SIZE })
  );
  const save = usePanelAction(panelPlansApi.savePlan, { invalidate: [["plans"]] });
  const remove = usePanelAction(panelPlansApi.deletePlan, { invalidate: [["plans"]] });

  const rows = query.data?.plans || [];
  const totalPages = query.data?.meta.total_pages || 1;

  useEffect(() => {
    setPage(1);
  }, [panelFilter, sort]);

  function openEdit(row: PanelPlanRow) {
    setDraft({
      plan_id: row.id,
      panel_code: row.panel_code,
      storage: row.storage,
      duration: row.duration,
      price: row.price,
      plan_type: row.plan_type,
      data_limit_reset_strategy: row.data_limit_reset_strategy,
      ip_limit: row.ip_limit,
      display_button_text: row.display_button_text || "",
      button_style: row.button_style || "",
      button_icon: row.button_icon ? String(row.button_icon) : "",
    });
    setCustomButton(Boolean(row.display_button_text || row.button_style || row.button_icon));
  }

  return (
    <>
      <PageHeader
        title={t("panel.common.salesPlans")}
        subtitle={t("panel.plans.subtitle")}
        action={
          <Button
            size="sm"
            disabled={!panels.length}
            onClick={() => {
              setDraft({ ...EMPTY_DRAFT, panel_code: panels[0]?.code || 0 });
              setCustomButton(false);
            }}
          >
            <Plus size={16} />
            {t("panel.common.addPlan")}
          </Button>
        }
      />

      {query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : (
        <SectionCard title={t("panel.common.plans")}>
          <div className="flex flex-wrap items-center gap-2">
            <IconMenuButton icon={Server} title={t("panel.common.panel")} active={panelFilter !== ""} badge={panelFilter !== ""} width={200} heightEstimate={220}>
              {(close) => (
                <>
                  <MenuHeader title={t("panel.common.panel")} />
                  <MenuRow
                    icon={Filter}
                    label={t("panel.common.allPanels")}
                    active={panelFilter === ""}
                    onClick={() => {
                      setPanelFilter("");
                      close();
                    }}
                  />
                  {panelOptions.map((opt) => (
                    <MenuRow
                      key={opt.value}
                      icon={Server}
                      label={opt.label}
                      active={opt.value === panelFilter}
                      onClick={() => {
                        setPanelFilter(opt.value);
                        close();
                      }}
                    />
                  ))}
                </>
              )}
            </IconMenuButton>

            <IconMenuButton icon={SlidersHorizontal} title={t("panel.plans.sortLabel")} active={sort !== "newest"} badge={sort !== "newest"} width={200} heightEstimate={320}>
              {(close) => (
                <>
                  <MenuHeader title={t("panel.plans.sortLabel")} />
                  {SORT_OPTIONS(t).map((opt) => (
                    <MenuRow
                      key={opt.value}
                      icon={opt.icon}
                      label={opt.label}
                      active={opt.value === sort}
                      onClick={() => {
                        setSort(opt.value);
                        close();
                      }}
                    />
                  ))}
                </>
              )}
            </IconMenuButton>

            {panelFilter && <Badge tone="primary">{panelOptions.find((p) => p.value === panelFilter)?.label}</Badge>}
            {sort !== "newest" && <Badge tone="muted">{SORT_OPTIONS(t).find((s) => s.value === sort)?.label}</Badge>}
          </div>

          {query.isLoading ? (
            <div className="mt-4 space-y-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full rounded-md" />
              ))}
            </div>
          ) : rows.length ? (
            <>
              <div className="mt-2 divide-y divide-border/60">
                {rows.map((row) => {
                  const orphaned = !row.panel;
                  const hasCustomButton = Boolean(row.display_button_text || row.button_style);
                  return (
                    <div key={row.id} className="flex flex-wrap items-center gap-3 py-3 first:pt-0 last:pb-0">
                      <IconBadge icon={orphaned ? AlertTriangle : HardDrive} tone={orphaned ? "danger" : "primary"} size="sm" />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 text-sm font-semibold text-text">
                          {row.storage ? `${row.storage} GB` : t("common.unlimited")}
                          <span className="text-xs font-normal text-muted">
                            · {t("panel.plans.durationDays", { count: row.duration })}
                          </span>
                        </div>
                        <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[11px] text-muted">
                          {orphaned ? (
                            <Badge tone="danger">{t("panel.plans.orphanPanel")}</Badge>
                          ) : (
                            <span className="inline-flex items-center gap-1">
                              <Server size={11} />
                              {row.panel}
                            </span>
                          )}
                          <Badge tone="muted">{planTypeLabels(t)[row.plan_type] || row.plan_type}</Badge>
                          {row.data_limit_reset_strategy !== "no_reset" && (
                            <Badge tone="muted">{resetLabels(t)[row.data_limit_reset_strategy] || row.data_limit_reset_strategy}</Badge>
                          )}
                          {row.ip_limit > 0 && <Badge tone="muted">IP {row.ip_limit}</Badge>}
                          {hasCustomButton && (
                            <span
                              className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium ${
                                STYLE_PREVIEW_CLASSES[row.button_style || ""]
                              }`}
                            >
                              {row.display_button_text || t("panel.common.default")}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="text-sm font-bold text-primary">{formatToman(row.price)}</div>
                      <div className="flex shrink-0 items-center gap-1">
                        <button
                          type="button"
                          title={t("common.edit")}
                          onClick={() => openEdit(row)}
                          className="flex h-8 w-8 items-center justify-center rounded-md border border-border text-muted transition-colors hover:border-primary/40 hover:bg-primary/10 hover:text-primary"
                        >
                          <Pencil size={14} />
                        </button>
                        <ConfirmButton
                          size="sm"
                          variant="ghost"
                          className="!h-8 !w-8 !px-0 text-danger hover:bg-danger/10"
                          title={t("common.delete")}
                          message={orphaned ? t("panel.plans.deleteOrphanConfirm") : t("panel.plans.deleteConfirm")}
                          onConfirm={() => remove.mutate({ plan_id: row.id })}
                        >
                          <Trash2 size={14} />
                        </ConfirmButton>
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="mt-4">
                <Pagination page={page} totalPages={totalPages} onChange={setPage} />
              </div>
            </>
          ) : (
            <p className="py-8 text-center text-sm text-muted">
              {panels.length ? t("panel.plans.empty") : t("panel.common.addPanelFirst")}
            </p>
          )}
        </SectionCard>
      )}

      <FormModal
        open={draft !== null}
        onClose={() => setDraft(null)}
        title={draft?.plan_id ? t("panel.plans.editTitle", { id: draft.plan_id }) : t("panel.common.addPlan")}
      >
        {draft && (
          <div className="space-y-4">
            <div>
              <p className="mb-2 text-xs font-semibold text-muted">{t("panel.common.panel")}</p>
              <PillGroup
                options={panelOptions}
                value={String(draft.panel_code)}
                onChange={(value) => setDraft({ ...draft, panel_code: Number(value) })}
              />
            </div>

            <div>
              <p className="mb-2 text-xs font-semibold text-muted">{t("panel.plans.sectionBasics")}</p>
              <div className="grid gap-3 sm:grid-cols-3">
                <Input
                  dense
                  label={t("panel.plans.volumeGb")}
                  inputMode="decimal"
                  value={String(draft.storage ?? 0)}
                  onChange={(event) => setDraft({ ...draft, storage: Number(event.target.value) || 0 })}
                />
                <Input
                  dense
                  label={t("panel.common.periodDays")}
                  inputMode="numeric"
                  value={String(draft.duration)}
                  onChange={(event) => setDraft({ ...draft, duration: Number(event.target.value) || 0 })}
                />
                <Input
                  dense
                  label={t("panel.plans.priceToman")}
                  inputMode="numeric"
                  value={String(draft.price)}
                  onChange={(event) => setDraft({ ...draft, price: Number(event.target.value) || 0 })}
                />
              </div>
            </div>

            <div>
              <p className="mb-2 text-xs font-semibold text-muted">{t("panel.plans.planType")}</p>
              <PillGroup
                options={(query.data?.plan_types || []).map((value) => ({ value, label: planTypeLabels(t)[value] || value }))}
                value={draft.plan_type || "volume"}
                onChange={(value) => setDraft({ ...draft, plan_type: value })}
              />
            </div>

            <div>
              <p className="mb-2 text-xs font-semibold text-muted">{t("panel.plans.volumeReset")}</p>
              <PillGroup
                options={(query.data?.reset_strategies || []).map((value) => ({ value, label: resetLabels(t)[value] || value }))}
                value={draft.data_limit_reset_strategy || "no_reset"}
                onChange={(value) => setDraft({ ...draft, data_limit_reset_strategy: value })}
              />
            </div>

            <div>
              <p className="mb-2 text-xs font-semibold text-muted">{t("panel.plans.ipLimit")}</p>
              <Input
                dense
                inputMode="numeric"
                value={String(draft.ip_limit ?? 0)}
                onChange={(event) => setDraft({ ...draft, ip_limit: Number(event.target.value) || 0 })}
                placeholder={t("panel.plans.noLimit")}
              />
            </div>

            <div>
              <Toggle
                checked={customButton}
                onChange={setCustomButton}
                label={t("panel.plans.sectionButton")}
                hint={t("panel.plans.customButtonHint")}
              />

              {customButton && (
                <div className="mt-3 space-y-3 rounded-lg border border-border bg-surface-2/40 p-3">
                  <Input
                    dense
                    label={t("panel.plans.buttonText")}
                    value={draft.display_button_text || ""}
                    onChange={(event) => setDraft({ ...draft, display_button_text: event.target.value })}
                  />
                  <div>
                    <p className="mb-1.5 text-xs text-muted">{t("panel.common.buttonColour")}</p>
                    <div className="flex items-center gap-2">
                      {(query.data?.button_styles || []).map((value) => {
                        const active = (draft.button_style || "") === value;
                        return (
                          <button
                            key={value || "default"}
                            type="button"
                            title={styleLabels(t)[value] || value}
                            onClick={() => setDraft({ ...draft, button_style: value })}
                            className={`flex h-8 w-8 items-center justify-center rounded-full border-2 transition-transform ${
                              STYLE_SWATCH_CLASSES[value]
                            } ${active ? "scale-110 ring-2 ring-offset-2 ring-offset-surface ring-current" : ""}`}
                          >
                            {active && <Check size={14} className={value ? "text-white" : "text-text"} />}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                  <Input
                    dense
                    label={t("panel.common.premiumEmojiId")}
                    ltr
                    inputMode="numeric"
                    value={draft.button_icon || ""}
                    onChange={(event) => setDraft({ ...draft, button_icon: event.target.value })}
                  />
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2 border-t border-border pt-3">
              <Button size="sm" variant="ghost" onClick={() => setDraft(null)}>
                {t("panel.common.dismiss")}
              </Button>
              <Button
                size="sm"
                loading={save.isPending}
                disabled={!draft.panel_code || !draft.duration}
                onClick={() => {
                  const payload = customButton
                    ? draft
                    : { ...draft, display_button_text: "", button_style: "", button_icon: "" };
                  save.mutate(payload, { onSuccess: () => setDraft(null) });
                }}
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


function PillGroup({
  options,
  value,
  onChange,
}: {
  options: { value: string; label: string }[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
              active ? "border-primary/40 bg-primary/12 text-primary" : "border-border text-muted hover:bg-surface-2 hover:text-text"
            }`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
