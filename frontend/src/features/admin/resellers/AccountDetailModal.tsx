import { useState } from "react";
import { Link } from "react-router-dom";
import { Copy, Eye, EyeOff, ExternalLink, KeyRound, Pause, Play, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Input, Skeleton } from "../../../components/ui";
import { useToast } from "../../../components/ui/Toast";
import { panelResellersApi } from "../../../api/panel";
import {
  clampPercent,
  copyToClipboard,
  formatBytes,
  formatNumber,
  formatToman,
  formatUnixDate,
} from "../../../lib/format";
import type { PanelResellerDetailResponse } from "../../../types/panel";
import { usePanelAction, usePanelQuery } from "../../../queries/usePanelApi";
import { ConfirmButton, FormModal, SelectField } from "../components";
import { Detail, EventList, Segmented, StatusBadge } from "./parts";
import { GB, formatRunway, pricingLabels, runwayTone } from "./labels";

type Navigate = (tab: string, extra?: Record<string, string>) => void;

const INVALIDATE = [["reseller"], ["resellers"], ["reseller-overview"], ["reseller-events"], ["reseller-ledger"]];

export default function AccountDetailModal({
  code,
  onClose,
  onNavigate,
}: {
  code: number | null;
  onClose: () => void;
  onNavigate: Navigate;
}) {
  const { t } = useTranslation();
  const detail = usePanelQuery(
    ["reseller", code],
    (auth) => panelResellersApi.getReseller({ ...auth, code: code as number }),
    { enabled: code !== null }
  );
  const account = detail.data?.reseller;

  return (
    <FormModal
      open={code !== null}
      onClose={onClose}
      size="xl"
      title={t("panel.resellers.detailTitle", { name: account?.username || code || "" })}
    >
      {detail.isLoading || (detail.isFetching && !detail.data) ? (
        <div className="space-y-3">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      ) : detail.data && account ? (
        <AccountBody key={account.code} data={detail.data} onClose={onClose} onNavigate={onNavigate} />
      ) : (
        <p className="py-6 text-center text-sm text-muted">{detail.error?.message || t("panel.resellers.notFound")}</p>
      )}
    </FormModal>
  );
}

function AccountBody({
  data,
  onClose,
  onNavigate,
}: {
  data: PanelResellerDetailResponse;
  onClose: () => void;
  onNavigate: Navigate;
}) {
  const { t } = useTranslation();
  const toast = useToast();
  const account = data.reseller!;
  const actions = new Set(data.actions);
  const live = data.live;
  const [history, setHistory] = useState<"events" | "ledger">("events");
  const [password, setPassword] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [renewPlan, setRenewPlan] = useState(String(data.renew_plans[0]?.id || ""));
  const [extendDays, setExtendDays] = useState("");
  const [capGb, setCapGb] = useState(account.usage_cap_bytes ? String(+(account.usage_cap_bytes / GB).toFixed(2)) : "");
  const [maxUsers, setMaxUsers] = useState(String(account.max_users || 0));

  const pause = usePanelAction(panelResellersApi.pauseReseller, { invalidate: INVALIDATE });
  const resume = usePanelAction(panelResellersApi.resumeReseller, { invalidate: INVALIDATE });
  const reveal = usePanelAction(panelResellersApi.revealPassword);
  const reset = usePanelAction(panelResellersApi.resetPassword, { invalidate: INVALIDATE });
  const renew = usePanelAction(panelResellersApi.renewReseller, { invalidate: INVALIDATE });
  const extend = usePanelAction(panelResellersApi.extendReseller, { invalidate: INVALIDATE });
  const cap = usePanelAction(panelResellersApi.setUsageCap, { invalidate: INVALIDATE });
  const limit = usePanelAction(panelResellersApi.setMaxUsers, { invalidate: INVALIDATE });
  const remove = usePanelAction(panelResellersApi.deleteReseller, { invalidate: INVALIDATE });

  const copy = (text: string) =>
    void copyToClipboard(text).then(() => toast.show(t("panel.resellerHub.detail.copied"), "success"));

  const togglePassword = () => {
    if (password !== null) {
      setShowPassword((value) => !value);
      return;
    }
    reveal.mutate(
      { code: account.code },
      {
        onSuccess: (result) => {
          setPassword(result.password || "");
          setShowPassword(true);
        },
      }
    );
  };

  const usedPercent = live && live.data_limit ? clampPercent(live.used_traffic, live.data_limit) : null;
  const isPayg = account.pricing_mode === "hourly" || account.pricing_mode === "usage";

  return (
    <div className="space-y-5">
      {/* Identity */}
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge status={account.status} />
        <Badge tone="primary">{pricingLabels(t)[account.pricing_mode] || account.pricing_mode}</Badge>
        {account.panel && <Badge tone="muted">{account.panel}</Badge>}
        {data.plan?.name && <Badge tone="muted">{data.plan.name}</Badge>}
        <Link
          to={`/panel/users/${account.telegram_id}`}
          className="ltr-field ms-auto flex items-center gap-1 text-xs text-muted hover:text-primary"
        >
          {account.telegram_id}
          <ExternalLink size={12} />
        </Link>
      </div>

      {/* Live panel data */}
      <section className="rounded-xl bg-surface-2/60 p-3.5">
        {live ? (
          <div className="space-y-3">
            <div>
              <div className="mb-1 flex items-center justify-between text-xs">
                <span className="text-muted">{t("panel.resellerHub.detail.traffic")}</span>
                <span className="text-text">
                  {formatBytes(live.used_traffic, 2)}
                  {live.data_limit ? ` / ${formatBytes(live.data_limit)}` : ` · ${t("panel.resellerHub.unlimited")}`}
                </span>
              </div>
              {usedPercent !== null && (
                <div className="h-2 overflow-hidden rounded-full bg-border/60">
                  <div
                    className={`h-full rounded-full ${usedPercent > 90 ? "bg-danger" : usedPercent > 70 ? "bg-warning" : "bg-primary"}`}
                    style={{ width: `${usedPercent}%` }}
                  />
                </div>
              )}
            </div>
            <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Detail
                label={t("panel.resellerHub.detail.users")}
                value={`${formatNumber(live.total_users)} / ${account.max_users ? formatNumber(account.max_users) : "∞"}`}
              />
              <Detail label={t("panel.resellerHub.detail.adminStatus")} value={live.admin_status || "—"} ltr />
              <Detail
                label={t("panel.common.expiry")}
                value={account.expiration_time ? formatUnixDate(account.expiration_time) : t("panel.resellerHub.unlimited")}
              />
              <Detail label={t("panel.resellerHub.detail.adminId")} value={account.panel_admin_id ?? "—"} ltr />
            </dl>
          </div>
        ) : (
          <p className="text-sm text-warning">{data.live_error || t("panel.resellerHub.detail.liveMissing")}</p>
        )}
        {data.grace_days_left !== null && data.grace_days_left !== undefined && (
          <p className="mt-3 rounded-md bg-danger/10 px-3 py-2 text-xs text-danger">
            {t("panel.resellerHub.detail.graceLeft", { count: formatNumber(data.grace_days_left) })}
          </p>
        )}
      </section>

      {/* Credentials */}
      <section className="space-y-2">
        <h3 className="text-xs font-semibold text-muted">{t("panel.resellerHub.detail.credentials")}</h3>
        <div className="grid gap-2 sm:grid-cols-2">
          {live?.login_url && live.login_url !== "—" && (
            <CopyRow label={t("panel.resellerHub.detail.loginUrl")} value={live.login_url} onCopy={copy} />
          )}
          <CopyRow label={t("panel.resellerHub.detail.username")} value={account.username || ""} onCopy={copy} />
          <div className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 sm:col-span-2">
            <KeyRound size={14} className="shrink-0 text-muted" />
            <span className="text-xs text-muted">{t("panel.resellerHub.detail.password")}</span>
            <button
              type="button"
              onClick={togglePassword}
              className="ltr-field min-w-0 flex-1 truncate text-start font-mono text-sm text-text"
            >
              {showPassword && password !== null ? password : "••••••••"}
            </button>
            <Button size="sm" variant="ghost" loading={reveal.isPending} onClick={togglePassword}>
              {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
            </Button>
            {showPassword && password && (
              <Button size="sm" variant="ghost" onClick={() => copy(password)}>
                <Copy size={14} />
              </Button>
            )}
            <ConfirmButton
              size="sm"
              variant="secondary"
              loading={reset.isPending}
              message={t("panel.resellerHub.detail.resetConfirm")}
              onConfirm={() =>
                reset.mutate(
                  { code: account.code },
                  {
                    onSuccess: (result) => {
                      setPassword(result.password || "");
                      setShowPassword(true);
                    },
                  }
                )
              }
            >
              {t("panel.resellerHub.detail.resetPassword")}
            </ConfirmButton>
          </div>
        </div>
      </section>

      {/* Wallet (pay-as-you-go) */}
      {isPayg && (
        <section className="grid grid-cols-2 gap-3 rounded-xl border border-border p-3.5 sm:grid-cols-4">
          <Detail label={t("panel.resellerHub.detail.balance")} value={formatToman(data.balance || 0)} />
          <Detail
            label={t("panel.resellerHub.detail.rate")}
            value={
              data.plan
                ? t(account.pricing_mode === "hourly" ? "panel.resellerHub.perHourAmount" : "panel.resellerHub.perGbAmount", {
                    amount: formatToman(data.plan.rate),
                  })
                : "—"
            }
          />
          <Detail label={t("panel.resellerHub.detail.billedTotal")} value={formatToman(data.billed_total || 0)} />
          <div>
            <dt className="text-xs text-muted">{t("panel.resellerHub.detail.runway")}</dt>
            <dd className="mt-1">
              <Badge tone={runwayTone(data.runway_hours, 24)}>{formatRunway(t, data.runway_hours)}</Badge>
            </dd>
          </div>
        </section>
      )}

      {/* Actions */}
      <section className="space-y-3">
        <h3 className="text-xs font-semibold text-muted">{t("panel.resellerHub.detail.actions")}</h3>
        <div className="flex flex-wrap gap-2">
          {actions.has("pause") && (
            <ConfirmButton
              size="sm"
              variant="secondary"
              loading={pause.isPending}
              message={t("panel.resellerHub.detail.pauseConfirm")}
              onConfirm={() => pause.mutate({ code: account.code })}
            >
              <Pause size={14} />
              {t("panel.resellerHub.detail.pause")}
            </ConfirmButton>
          )}
          {actions.has("resume") && (
            <Button size="sm" variant="secondary" loading={resume.isPending} onClick={() => resume.mutate({ code: account.code })}>
              <Play size={14} />
              {t("panel.resellerHub.detail.resume")}
            </Button>
          )}
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          {actions.has("renew") && (
            <ActionBox title={t("panel.resellerHub.detail.renew")} hint={t("panel.resellerHub.detail.renewHint")}>
              {data.renew_plans.length ? (
                <div className="flex items-end gap-2">
                  <div className="min-w-0 flex-1">
                    <SelectField
                      label={t("panel.resellerHub.detail.plan")}
                      options={data.renew_plans.map((plan) => ({
                        value: String(plan.id),
                        label: `${plan.name || `#${plan.id}`} · ${formatToman(plan.rate)}`,
                      }))}
                      value={renewPlan}
                      onChange={(event) => setRenewPlan(event.target.value)}
                    />
                  </div>
                  <ConfirmButton
                    size="md"
                    loading={renew.isPending}
                    disabled={!renewPlan}
                    message={t("panel.resellerHub.detail.renewConfirm")}
                    onConfirm={() => renew.mutate({ code: account.code, plan_id: Number(renewPlan) })}
                  >
                    {t("panel.resellerHub.detail.renewButton")}
                  </ConfirmButton>
                </div>
              ) : (
                <p className="text-xs text-muted">{t("panel.resellerHub.detail.noRenewPlans")}</p>
              )}
            </ActionBox>
          )}

          {actions.has("extend") && (
            <ActionBox title={t("panel.resellerHub.detail.extend")} hint={t("panel.resellerHub.detail.extendHint")}>
              <div className="flex items-end gap-2">
                <Input
                  label={t("panel.resellerHub.detail.days")}
                  inputMode="numeric"
                  value={extendDays}
                  placeholder={t("panel.common.egThirty")}
                  onChange={(event) => setExtendDays(event.target.value.replace(/\D/g, ""))}
                />
                <Button
                  size="md"
                  variant="secondary"
                  loading={extend.isPending}
                  disabled={!Number(extendDays)}
                  onClick={() =>
                    extend.mutate({ code: account.code, days: Number(extendDays) }, { onSuccess: () => setExtendDays("") })
                  }
                >
                  {t("panel.resellerHub.detail.apply")}
                </Button>
              </div>
            </ActionBox>
          )}

          {actions.has("usage_cap") && (
            <ActionBox title={t("panel.resellers.usageCap")} hint={t("panel.resellerHub.detail.capHint")}>
              <div className="flex items-end gap-2">
                <Input
                  label={t("panel.resellers.usageCapGb")}
                  inputMode="decimal"
                  value={capGb}
                  placeholder={t("panel.resellers.emptyMeansNoCap")}
                  onChange={(event) => setCapGb(event.target.value)}
                />
                <Button
                  size="md"
                  variant="secondary"
                  loading={cap.isPending}
                  onClick={() => cap.mutate({ code: account.code, usage_cap_gb: capGb.trim() ? Number(capGb) || 0 : null })}
                >
                  {t("panel.resellerHub.detail.apply")}
                </Button>
              </div>
            </ActionBox>
          )}

          {actions.has("max_users") && (
            <ActionBox title={t("panel.common.maxUsers")} hint={t("panel.resellerHub.detail.maxUsersHint")}>
              <div className="flex items-end gap-2">
                <Input
                  label={t("panel.resellerHub.detail.userLimit")}
                  inputMode="numeric"
                  value={maxUsers}
                  onChange={(event) => setMaxUsers(event.target.value.replace(/\D/g, ""))}
                />
                <Button
                  size="md"
                  variant="secondary"
                  loading={limit.isPending}
                  onClick={() => limit.mutate({ code: account.code, max_users: Number(maxUsers) || 0 })}
                >
                  {t("panel.resellerHub.detail.apply")}
                </Button>
              </div>
            </ActionBox>
          )}
        </div>
      </section>

      {/* History */}
      <section className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <Segmented
            items={[
              { value: "events", label: t("panel.resellerHub.billing.events") },
              { value: "ledger", label: t("panel.resellerHub.billing.ledger") },
            ]}
            value={history}
            onChange={(value) => setHistory(value as "events" | "ledger")}
          />
          <Button
            size="sm"
            variant="ghost"
            onClick={() => onNavigate("billing", { view: history, account: String(account.code) })}
          >
            {t("panel.resellerHub.detail.fullHistory")}
          </Button>
        </div>
        {history === "events" ? (
          <EventList events={data.events} />
        ) : data.snapshots.length ? (
          <ul className="space-y-1.5 text-sm">
            {data.snapshots.map((snapshot) => (
              <li key={snapshot.id} className="flex items-center justify-between gap-3 rounded-md bg-surface-2 px-3 py-2">
                <span className="text-xs text-muted">{snapshot.snapshot_at ? formatUnixDate(snapshot.snapshot_at) : "—"}</span>
                <span className="text-xs text-muted">
                  {snapshot.kind === "hourly"
                    ? t("panel.resellerHub.billing.minutes", { count: formatNumber(snapshot.billed_minutes || 0) })
                    : formatBytes(snapshot.used_traffic, 2)}
                </span>
                <span className="font-medium">{formatToman(snapshot.billed_amount)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted">{t("panel.resellers.invoicesEmpty")}</p>
        )}
      </section>

      {/* Danger zone */}
      {actions.has("delete") && (
        <section className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-danger/30 bg-danger/5 p-3.5">
          <div>
            <p className="text-sm font-medium text-danger">{t("panel.resellerHub.detail.deleteTitle")}</p>
            <p className="mt-0.5 text-xs text-muted">{t("panel.resellerHub.detail.deleteHint")}</p>
          </div>
          <ConfirmButton
            size="sm"
            variant="danger"
            loading={remove.isPending}
            message={t("panel.resellerHub.detail.deleteConfirm", { name: account.username })}
            onConfirm={() => remove.mutate({ code: account.code }, { onSuccess: onClose })}
          >
            <Trash2 size={14} />
            {t("common.delete")}
          </ConfirmButton>
        </section>
      )}
    </div>
  );
}

function CopyRow({ label, value, onCopy }: { label: string; value: string; onCopy: (value: string) => void }) {
  return (
    <button
      type="button"
      onClick={() => onCopy(value)}
      className="flex min-w-0 items-center gap-2 rounded-lg border border-border px-3 py-2 text-start hover:border-primary/40"
    >
      <span className="shrink-0 text-xs text-muted">{label}</span>
      <span className="ltr-field min-w-0 flex-1 truncate text-sm text-text">{value || "—"}</span>
      <Copy size={13} className="shrink-0 text-muted" />
    </button>
  );
}

function ActionBox({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-border p-3">
      <p className="text-sm font-medium text-text">{title}</p>
      {hint && <p className="mb-2 mt-0.5 text-xs text-muted">{hint}</p>}
      {children}
    </div>
  );
}
