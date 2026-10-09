import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Copy, Eye, EyeOff, ExternalLink, KeyRound, Pause, Play, RefreshCw, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
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
import type { PanelResellerDetailResponse, PanelResellerRow } from "../../../types/panel";
import { usePanelAction, usePanelQuery } from "../../../queries/usePanelApi";
import { ConfirmButton, FormModal, SelectField } from "../components";
import { ChargeItem } from "../../../components/ChargeItem";
import { Detail, EventList, Segmented, StatusBadge, toCharge } from "./parts";
import { GB, formatRunway, pricingLabels, pricingShortLabels, runwayTone } from "./labels";
import { HOURLY, USAGE, ruleFor } from "./planRules";

type Navigate = (tab: string, extra?: Record<string, string>) => void;

const DAY = 86400;

/** One line of what the account's plan type means for it right now, e.g. «ثابت · تمدید با همین پلن · ۱۸ روز تا انقضا، سپس ۷ روز مهلت». */
function ruleSummary(t: TFunction, account: PanelResellerRow, data: PanelResellerDetailResponse): string {
  const key = "panel.resellerHub.detail.summary";
  const rule = ruleFor(account.pricing_mode);
  const parts = [pricingShortLabels(t)[account.pricing_mode] || account.pricing_mode];
  if (rule.renewable && account.plan_id) parts.push(t(`${key}.renewSame`));
  if (account.pricing_mode === USAGE) parts.push(t(`${key}.usage`));
  if (account.pricing_mode === HOURLY) parts.push(t(`${key}.hourly`));
  if (account.expiration_time) {
    const left = account.expiration_time - Date.now() / 1000;
    if (account.status === "expired" || left <= 0) {
      parts.push(
        data.grace_days_left !== null && data.grace_days_left !== undefined
          ? t(`${key}.expiredGrace`, { count: formatNumber(data.grace_days_left) })
          : t(`${key}.expired`)
      );
    } else {
      const days = formatNumber(Math.max(1, Math.ceil(left / DAY)));
      parts.push(
        data.grace_days
          ? t(`${key}.expiresGrace`, { days, grace: formatNumber(data.grace_days) })
          : t(`${key}.expires`, { days })
      );
    }
  } else if (!rule.renewable) {
    parts.push(t(`${key}.noExpiry`));
  }
  return parts.join(" · ");
}

/** «۵۰ پلن + ۱۰ اضافه» when the reseller bought slots, otherwise the plain limit (∞ for none). */
function userLimitLabel(t: TFunction, account: PanelResellerRow): string {
  const limit = account.max_users || 0;
  if (!limit) return "∞";
  const extra = account.extra_users || 0;
  if (extra <= 0) return formatNumber(limit);
  return t("panel.resellerHub.detail.usersSplit", {
    plan: formatNumber(Math.max(0, limit - extra)),
    extra: formatNumber(extra),
  });
}

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
  const changePlans = data.change_plans || [];
  const ownPlan = data.renew_plans[0];
  const [changePlanId, setChangePlanId] = useState(String(changePlans[0]?.id || ""));
  const [extendDays, setExtendDays] = useState("");
  const [volumeMode, setVolumeMode] = useState<"add" | "set">(account.data_limit ? "add" : "set");
  const [volumeGb, setVolumeGb] = useState("");
  const [capGb, setCapGb] = useState(account.usage_cap_bytes ? String(+(account.usage_cap_bytes / GB).toFixed(2)) : "");
  const [maxUsers, setMaxUsers] = useState(String(account.max_users || 0));

  // After a tool runs the detail is refetched; follow the new values instead of keeping stale inputs.
  const changePlanIds = changePlans.map((plan) => plan.id).join(",");
  useEffect(() => {
    setChangePlanId((current) =>
      changePlans.some((plan) => String(plan.id) === current) ? current : String(changePlans[0]?.id || "")
    );
  }, [changePlanIds]); // changePlans is a new array on each render; its ids are the real dependency
  useEffect(() => setMaxUsers(String(account.max_users || 0)), [account.max_users]);
  useEffect(() => {
    if (!account.data_limit) setVolumeMode("set");
  }, [account.data_limit]);

  const pause = usePanelAction(panelResellersApi.pauseReseller, { invalidate: INVALIDATE });
  const resume = usePanelAction(panelResellersApi.resumeReseller, { invalidate: INVALIDATE });
  const reveal = usePanelAction(panelResellersApi.revealPassword);
  const reset = usePanelAction(panelResellersApi.resetPassword, { invalidate: INVALIDATE });
  const renew = usePanelAction(panelResellersApi.renewReseller, { invalidate: INVALIDATE });
  const extend = usePanelAction(panelResellersApi.extendReseller, { invalidate: INVALIDATE });
  const cap = usePanelAction(panelResellersApi.setUsageCap, { invalidate: INVALIDATE });
  const limit = usePanelAction(panelResellersApi.setMaxUsers, { invalidate: INVALIDATE });
  const remove = usePanelAction(panelResellersApi.deleteReseller, { invalidate: INVALIDATE });
  const volume = usePanelAction(panelResellersApi.setDataLimit, { invalidate: INVALIDATE });
  const changePlan = usePanelAction(panelResellersApi.changePlan, { invalidate: INVALIDATE });
  const resync = usePanelAction(panelResellersApi.resyncReseller, { invalidate: INVALIDATE });
  const forgive = usePanelAction(panelResellersApi.forgiveUsage, { invalidate: INVALIDATE });

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
  const isPayg = account.pricing_mode === HOURLY || account.pricing_mode === USAGE;
  const currentLimit = account.data_limit || 0;
  const volumeValue = Number(volumeGb.replace(/[^\d.]/g, "")) || 0;
  const volumeAfter = volumeMode === "add" ? currentLimit + volumeValue * GB : volumeValue * GB;
  const targetPlan = changePlans.find((plan) => String(plan.id) === changePlanId);

  return (
    <div className="space-y-5">
      {/* Identity */}
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge status={account.status} />
        <Badge tone="primary">{pricingShortLabels(t)[account.pricing_mode] || account.pricing_mode}</Badge>
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

      <p className="-mt-3 text-xs leading-6 text-muted" title={pricingLabels(t)[account.pricing_mode] || account.pricing_mode}>
        {ruleSummary(t, account, data)}
      </p>

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
                value={`${formatNumber(live.total_users)} / ${userLimitLabel(t, account)}`}
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
                ? t(account.pricing_mode === HOURLY ? "panel.resellerHub.perHourAmount" : "panel.resellerHub.perGbUsedAmount", {
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
          {actions.has("resync") && (
            <ConfirmButton
              size="sm"
              variant="secondary"
              loading={resync.isPending}
              message={t("panel.resellerHub.detail.resyncConfirm")}
              onConfirm={() => resync.mutate({ code: account.code })}
            >
              <RefreshCw size={14} />
              {t("panel.resellerHub.detail.resync")}
            </ConfirmButton>
          )}
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          {actions.has("renew") && (
            <ActionBox title={t("panel.resellerHub.detail.renew")} hint={t("panel.resellerHub.detail.renewOwnHint")}>
              {ownPlan ? (
                <div className="flex items-end justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate text-sm text-text">{ownPlan.name || `${t("panel.resellerHub.plans.plan")} #${ownPlan.id}`}</p>
                    <p className="mt-0.5 text-xs text-muted">
                      {formatToman(ownPlan.rate)}
                      {ownPlan.duration > 0 && ` · ${t("panel.plans.durationDays", { count: formatNumber(ownPlan.duration) })}`}
                      {ownPlan.data_limit_gb > 0 && ` · ${formatNumber(ownPlan.data_limit_gb)} GB`}
                    </p>
                    {!ownPlan.enable && (
                      <p className="mt-1 text-xs text-warning">{t("panel.resellerHub.detail.renewDisabledPlan")}</p>
                    )}
                  </div>
                  <ConfirmButton
                    size="md"
                    loading={renew.isPending}
                    message={t(
                      ownPlan.data_limit_gb > 0
                        ? "panel.resellerHub.detail.renewConfirmVolume"
                        : "panel.resellerHub.detail.renewConfirmDays",
                      {
                        amount: formatToman(ownPlan.rate),
                        days: formatNumber(ownPlan.duration),
                        gb: formatNumber(ownPlan.data_limit_gb),
                      }
                    )}
                    onConfirm={() => renew.mutate({ code: account.code, plan_id: ownPlan.id })}
                  >
                    {t("panel.resellerHub.detail.renewButton")}
                  </ConfirmButton>
                </div>
              ) : (
                <p className="text-xs text-muted">{t("panel.resellerHub.detail.noOwnPlan")}</p>
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
                <ConfirmButton
                  size="md"
                  variant="secondary"
                  loading={extend.isPending}
                  disabled={!Number(extendDays)}
                  message={t("panel.resellerHub.detail.extendConfirm", { count: formatNumber(Number(extendDays) || 0) })}
                  onConfirm={() =>
                    extend.mutate({ code: account.code, days: Number(extendDays) }, { onSuccess: () => setExtendDays("") })
                  }
                >
                  {t("panel.resellerHub.detail.apply")}
                </ConfirmButton>
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
            <ActionBox title={t("panel.common.maxUsers")} hint={t("panel.resellerHub.detail.maxUsersTotalHint")}>
              <div className="flex items-end gap-2">
                <Input
                  label={t("panel.resellerHub.detail.userLimit")}
                  inputMode="numeric"
                  value={maxUsers}
                  onChange={(event) => setMaxUsers(event.target.value.replace(/\D/g, ""))}
                />
                <ConfirmButton
                  size="md"
                  variant="secondary"
                  loading={limit.isPending}
                  message={
                    Number(maxUsers) > 0
                      ? t("panel.resellerHub.detail.maxUsersConfirm", { count: formatNumber(Number(maxUsers)) })
                      : t("panel.resellerHub.detail.maxUsersUnlimitedConfirm")
                  }
                  onConfirm={() => limit.mutate({ code: account.code, max_users: Number(maxUsers) || 0 })}
                >
                  {t("panel.resellerHub.detail.apply")}
                </ConfirmButton>
              </div>
            </ActionBox>
          )}

          {actions.has("data_limit") && (
            <ActionBox title={t("panel.resellerHub.detail.volume")} hint={t("panel.resellerHub.detail.volumeHint")}>
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <Segmented
                  items={[
                    { value: "add", label: t("panel.resellerHub.detail.volumeAdd") },
                    { value: "set", label: t("panel.resellerHub.detail.volumeSet") },
                  ]}
                  value={volumeMode}
                  onChange={(value) => setVolumeMode(value as "add" | "set")}
                />
                <span className="text-xs text-muted">
                  {t("panel.resellerHub.detail.volumeCurrent", {
                    value: currentLimit ? formatBytes(currentLimit) : t("panel.resellerHub.unlimited"),
                  })}
                </span>
              </div>
              {volumeMode === "add" && !currentLimit ? (
                <p className="text-xs text-warning">{t("panel.resellerHub.detail.volumeAddUnlimited")}</p>
              ) : (
                <div className="flex items-end gap-2">
                  <Input
                    label={t("panel.resellerHub.detail.volumeGb")}
                    inputMode="decimal"
                    value={volumeGb}
                    onChange={(event) => setVolumeGb(event.target.value.replace(/[^\d.]/g, ""))}
                  />
                  <ConfirmButton
                    size="md"
                    variant="secondary"
                    loading={volume.isPending}
                    disabled={volumeValue <= 0}
                    message={t("panel.resellerHub.detail.volumeConfirm", {
                      before: currentLimit ? formatBytes(currentLimit) : t("panel.resellerHub.unlimited"),
                      after: formatBytes(volumeAfter),
                    })}
                    onConfirm={() =>
                      volume.mutate(
                        volumeMode === "add"
                          ? { code: account.code, add_gb: volumeValue }
                          : { code: account.code, set_gb: volumeValue },
                        { onSuccess: () => setVolumeGb("") }
                      )
                    }
                  >
                    {t("panel.resellerHub.detail.apply")}
                  </ConfirmButton>
                </div>
              )}
            </ActionBox>
          )}

          {actions.has("change_plan") && (
            <ActionBox title={t("panel.resellerHub.detail.changePlan")} hint={t("panel.resellerHub.detail.changePlanHint")}>
              {changePlans.length ? (
                <div className="flex items-end gap-2">
                  <div className="min-w-0 flex-1">
                    <SelectField
                      label={t("panel.resellerHub.detail.plan")}
                      options={changePlans.map((plan) => ({
                        value: String(plan.id),
                        label: [
                          plan.name || `#${plan.id}`,
                          plan.max_users > 0
                            ? t("panel.resellerHub.plans.users", { count: formatNumber(plan.max_users) })
                            : null,
                          plan.enable ? null : t("panel.common.inactive"),
                        ]
                          .filter(Boolean)
                          .join(" · "),
                      }))}
                      value={changePlanId}
                      onChange={(event) => setChangePlanId(event.target.value)}
                    />
                  </div>
                  <ConfirmButton
                    size="md"
                    variant="secondary"
                    loading={changePlan.isPending}
                    disabled={!targetPlan}
                    message={t("panel.resellerHub.detail.changePlanConfirm", {
                      name: targetPlan?.name || `#${targetPlan?.id ?? ""}`,
                    })}
                    onConfirm={() => targetPlan && changePlan.mutate({ code: account.code, plan_id: targetPlan.id })}
                  >
                    {t("panel.resellerHub.detail.apply")}
                  </ConfirmButton>
                </div>
              ) : (
                <p className="text-xs text-muted">{t("panel.resellerHub.detail.noChangePlans")}</p>
              )}
            </ActionBox>
          )}

          {actions.has("forgive_usage") && (
            <ActionBox title={t("panel.resellerHub.detail.forgive")} hint={t("panel.resellerHub.detail.forgiveHint")}>
              <ConfirmButton
                size="sm"
                variant="secondary"
                loading={forgive.isPending}
                message={t("panel.resellerHub.detail.forgiveConfirm")}
                onConfirm={() => forgive.mutate({ code: account.code })}
              >
                {t("panel.resellerHub.detail.forgiveButton")}
              </ConfirmButton>
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
          <ul className="space-y-2">
            {data.snapshots.map((snapshot) => (
              <ChargeItem key={snapshot.id} charge={toCharge(snapshot)} panelCounter={snapshot.used_traffic} />
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
