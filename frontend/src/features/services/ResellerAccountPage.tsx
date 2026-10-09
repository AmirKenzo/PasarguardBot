import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  ArrowRight,
  CalendarPlus,
  Eye,
  Gauge,
  HardDriveDownload,
  KeyRound,
  Pause,
  Play,
  RefreshCw,
  Store,
  Trash2,
  UserPlus,
  type LucideIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge, Button, Card, CopyField, IconBadge, Input, Sheet, SkeletonCard } from "../../components/ui";
import { ErrorState } from "../../components/ui/EmptyState";
import { ChargeItem } from "../../components/ChargeItem";
import {
  ResellerModeBadge,
  ResellerPlanFeatureList,
  ResellerPlanGuide,
  resolvePlanFeatures,
} from "../../components/ResellerPlanGuide";
import { useToast } from "../../components/ui/Toast";
import { resellerApi } from "../../api/webapp";
import { useTelegram } from "../../hooks/useTelegram";
import { clampPercent, formatBytes, formatNumber, formatRelativeTime, formatToman, formatUnixDate } from "../../lib/format";
import {
  EVENT_TONE,
  STATUS_TONE,
  eventAmount,
  eventLabels,
  formatRunway,
  resellerModeLabel,
  runwayTone,
  statusLabels,
} from "../../lib/resellerLabels";
import {
  useResellerAccount,
  useResellerEvents,
  useResellerMutation,
  useResellerUsage,
} from "../../queries/useReseller";
import type {
  ResellerAddonKind,
  ResellerEventItem,
  WebAppResellerAccountResponse,
  WebAppResellerAddonPreviewResponse,
  WebAppResellerRenewPreviewResponse,
} from "../../types/webapp";

type SheetKind = "password" | "status" | "renew" | "cap" | "delete" | ResellerAddonKind | null;
const GB = 1024 ** 3;
const DAY = 86400;
const ADDON_FALLBACK_MAX: Record<ResellerAddonKind, number> = {
  extra_days: 3650,
  extra_volume: 100_000,
  buy_user_capacity: 10_000,
};

const DOT: Record<string, string> = {
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  primary: "bg-primary",
  muted: "bg-muted",
};

/** Whole days until ``timestamp``; 0 once it has passed. */
function daysUntil(timestamp: number | null | undefined): number | null {
  if (!timestamp) return null;
  return Math.max(0, Math.ceil((timestamp - Date.now() / 1000) / DAY));
}

function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="min-w-0">
      <p className="truncate text-[11px] text-muted">{label}</p>
      <p className="mt-0.5 truncate text-sm font-bold text-text">{value}</p>
      {hint && <p className="mt-0.5 text-[10.5px] leading-4 text-muted">{hint}</p>}
    </div>
  );
}

function ActionTile({
  icon,
  label,
  tone = "primary",
  onClick,
}: {
  icon: LucideIcon;
  label: string;
  tone?: "primary" | "danger" | "warning" | "success";
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex flex-col items-center gap-2 rounded-lg border border-border bg-surface p-3 text-center transition-colors hover:border-primary/30"
    >
      <IconBadge icon={icon} tone={tone} size="sm" />
      <span className="text-xs font-semibold text-text">{label}</span>
    </button>
  );
}

function EventRow({ event }: { event: ResellerEventItem }) {
  const { t } = useTranslation();
  const amount = eventAmount(event.data);
  return (
    <li className="flex items-start gap-3 py-2.5">
      <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${DOT[EVENT_TONE[event.kind] || "muted"]}`} />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-text">{eventLabels(t)[event.kind] || event.title}</p>
        <p className="mt-0.5 text-xs text-muted" title={formatUnixDate(event.created_at)}>
          {formatRelativeTime(event.created_at)}
        </p>
      </div>
      {amount > 0 && <span className="shrink-0 text-sm font-semibold text-text">{formatToman(amount)}</span>}
    </li>
  );
}

function History({ code, showUsage }: { code: number; showUsage: boolean }) {
  const { t } = useTranslation();
  const [view, setView] = useState<"events" | "usage">("events");
  const [page, setPage] = useState(1);
  const events = useResellerEvents(code, page, view === "events");
  const usage = useResellerUsage(code, page, view === "usage" && showUsage);
  const pageCount = Math.max(1, Math.ceil((events.data?.total ?? 0) / 15));

  const switchTo = (next: "events" | "usage") => {
    setView(next);
    setPage(1);
  };

  return (
    <Card className="p-4">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-bold text-text">{t("reseller.detail.history")}</h3>
        {showUsage && (
          <div className="inline-flex rounded-lg bg-surface-2 p-0.5">
            {(["events", "usage"] as const).map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => switchTo(item)}
                className={`rounded-md px-3 py-1 text-xs font-medium ${
                  view === item ? "bg-surface text-primary shadow-sm" : "text-muted"
                }`}
              >
                {t(item === "events" ? "reseller.detail.events" : "reseller.detail.usage")}
              </button>
            ))}
          </div>
        )}
      </div>

      {view === "events" ? (
        events.data?.events.length ? (
          <ul className="divide-y divide-border/60">
            {events.data.events.map((event) => (
              <EventRow key={event.id} event={event} />
            ))}
          </ul>
        ) : (
          <p className="py-6 text-center text-sm text-muted">
            {events.isLoading ? t("reseller.loading") : t("reseller.detail.noEvents")}
          </p>
        )
      ) : usage.data?.rows.length ? (
        <>
          <p className="mb-2 text-xs text-muted">
            {t("reseller.detail.totalBilled", { amount: formatToman(usage.data.total_billed) })}
          </p>
          <ul className="space-y-2">
            {usage.data.rows.map((row) => (
              <ChargeItem key={`${row.snapshot_at}-${row.kind}`} charge={{ ...row, charged_at: row.snapshot_at }} />
            ))}
          </ul>
        </>
      ) : (
        <p className="py-6 text-center text-sm text-muted">
          {usage.isLoading ? t("reseller.loading") : t("reseller.detail.noUsage")}
        </p>
      )}

      {(view === "events" ? pageCount > 1 : page > 1 || usage.data?.has_more) && (
        <div className="mt-3 flex items-center justify-between">
          <Button size="sm" variant="ghost" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>
            {t("ui.prev")}
          </Button>
          <span className="text-xs text-muted">{t("ui.page", { page: formatNumber(page) })}</span>
          <Button
            size="sm"
            variant="ghost"
            disabled={view === "events" ? page >= pageCount : !usage.data?.has_more}
            onClick={() => setPage((value) => value + 1)}
          >
            {t("ui.next")}
          </Button>
        </div>
      )}
    </Card>
  );
}

export default function ResellerAccountPage() {
  const { t } = useTranslation();
  const { code: codeParam } = useParams();
  const code = Number(codeParam) || null;
  const query = useResellerAccount(code);

  return (
    <div>
      <PageHeader
        title={query.data?.account?.username || t("reseller.detail.title")}
        back="/services?tab=reseller"
      />
      {query.isLoading ? (
        <div className="space-y-3">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : query.error || !query.data?.account ? (
        <ErrorState
          message={(query.error as Error)?.message || t("reseller.detail.notFound")}
          onRetry={() => void query.refetch()}
        />
      ) : (
        <AccountView data={query.data} />
      )}
    </div>
  );
}

function AccountView({ data }: { data: WebAppResellerAccountResponse }) {
  const { t } = useTranslation();
  const { haptic } = useTelegram();
  const toast = useToast();
  const navigate = useNavigate();
  const account = data.account!;
  const actions = new Set(data.actions);
  const [sheet, setSheet] = useState<SheetKind>(null);
  const [password, setPassword] = useState<string | null>(null);

  const reveal = useResellerMutation(resellerApi.revealPassword, { refresh: false });
  const reset = useResellerMutation(resellerApi.resetPassword);
  const pause = useResellerMutation(resellerApi.pause);
  const resume = useResellerMutation(resellerApi.resume);
  const remove = useResellerMutation(resellerApi.deleteAccount);

  const isPayg = account.pricing_mode === "hourly" || account.pricing_mode === "usage";
  const usedPercent = data.data_limit_bytes ? clampPercent(data.used_traffic_bytes, data.data_limit_bytes) : null;
  const capPercent = data.usage_cap_bytes ? clampPercent(data.used_traffic_bytes, data.usage_cap_bytes) : null;

  // Volume left of the total; carried-over and extra volume are not tracked apart, so only the total is shown.
  const remainingBytes = data.data_limit_bytes ? Math.max(0, data.data_limit_bytes - data.used_traffic_bytes) : null;
  const daysLeft = daysUntil(account.expiration_timestamp);
  // The guide describes this account: its own user limit (an admin may have changed it), not the plan's.
  const accountPlan = data.plan ? { ...data.plan, max_users: account.max_users } : null;
  const extraUsers = data.extra_users ?? account.extra_users ?? 0;
  const planUsers = data.plan_max_users ?? 0;

  const fail = (err: unknown) => {
    haptic.notify("error");
    toast.show((err as Error).message, "error");
  };
  const done = (message?: string | null) => {
    haptic.notify("success");
    if (message) toast.show(message, "success");
    setSheet(null);
  };

  const revealPassword = () => {
    haptic.select();
    reveal.mutate({ code: account.code }, { onSuccess: (res) => setPassword(res.password ?? ""), onError: fail });
  };

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
      {/* Identity */}
      <Card className="flex items-center gap-3 p-4">
        <IconBadge icon={Store} tone="primary" size="lg" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-base font-extrabold text-text" dir="ltr" style={{ textAlign: "start" }}>
            {account.username}
          </p>
          <p className="mt-0.5 truncate text-xs text-muted">
            {[account.panel_name, resellerModeLabel(t, account.pricing_mode), `#${account.code}`]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        <Badge tone={STATUS_TONE[account.status] || "muted"}>{statusLabels(t)[account.status] || account.status}</Badge>
      </Card>

      {data.admin_locked && (
        <p className="rounded-md border border-danger/25 bg-danger/5 px-4 py-3 text-sm text-danger">
          {t("reseller.detail.adminLocked")}
        </p>
      )}
      {data.grace_days_left != null && (
        <p className="rounded-md border border-danger/25 bg-danger/5 px-4 py-3 text-sm text-danger">
          {t("reseller.detail.graceLeft", { count: formatNumber(data.grace_days_left) })}
        </p>
      )}
      {account.status === "paused" && (
        <p className="rounded-md border border-border bg-surface-2 px-4 py-3 text-sm text-muted">
          {t("reseller.detail.pausedNote")}
        </p>
      )}
      {account.status === "suspended" && isPayg && (
        <p className="rounded-md border border-warning/25 bg-warning/5 px-4 py-3 text-sm text-warning">
          {t("reseller.detail.suspendedNote")}
        </p>
      )}
      {account.status === "usage_capped" && (
        <p className="rounded-md border border-warning/25 bg-warning/5 px-4 py-3 text-sm text-warning">
          {t("reseller.detail.cappedNote")}
        </p>
      )}

      {/* Usage */}
      <Card className="space-y-3 p-4">
        {data.live ? (
          <>
            <div>
              <div className="mb-1.5 flex items-center justify-between text-xs">
                <span className="text-muted">{t("reseller.detail.traffic")}</span>
                <span className="font-semibold text-text">
                  {formatBytes(data.used_traffic_bytes, 2)}
                  {data.data_limit_bytes ? ` / ${formatBytes(data.data_limit_bytes)}` : ""}
                </span>
              </div>
              {usedPercent !== null && (
                <div className="h-2 overflow-hidden rounded-full bg-surface-2">
                  <div
                    className={`h-full rounded-full ${usedPercent > 90 ? "bg-danger" : usedPercent > 70 ? "bg-warning" : "bg-primary"}`}
                    style={{ width: `${usedPercent}%` }}
                  />
                </div>
              )}
            </div>
            {capPercent !== null && (
              <div>
                <div className="mb-1.5 flex items-center justify-between text-xs">
                  <span className="text-muted">{t("reseller.detail.usageCap")}</span>
                  <span className="font-semibold text-text">{formatBytes(data.usage_cap_bytes ?? 0)}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-surface-2">
                  <div className="h-full rounded-full bg-warning" style={{ width: `${capPercent}%` }} />
                </div>
              </div>
            )}
          </>
        ) : (
          <p className="text-sm text-warning">{t("reseller.detail.liveMissing")}</p>
        )}
        <div className="grid grid-cols-2 gap-3 border-t border-border pt-3 sm:grid-cols-4">
          {data.live && (
            <Stat
              label={t("reseller.detail.remaining")}
              value={
                remainingBytes !== null
                  ? formatBytes(remainingBytes, 2)
                  : isPayg
                    ? t("reseller.plan.noVolumeCap")
                    : t("reseller.detail.unlimitedVolume")
              }
              hint={
                remainingBytes === null
                  ? undefined
                  : t("reseller.detail.remainingOf", { total: formatBytes(data.data_limit_bytes) })
              }
            />
          )}
          <Stat
            label={t("reseller.detail.daysLeft")}
            value={
              daysLeft === null
                ? t("reseller.noExpiry")
                : daysLeft > 0
                  ? t("renewFlow.days", { count: formatNumber(daysLeft) })
                  : t("reseller.detail.expiredValue")
            }
            hint={account.expiration_timestamp ? formatUnixDate(account.expiration_timestamp) : undefined}
          />
          <Stat
            label={t("reseller.detail.users")}
            value={`${formatNumber(data.total_users)} / ${account.max_users ? formatNumber(account.max_users) : "∞"}`}
            hint={
              extraUsers > 0 && planUsers > 0
                ? t("reseller.detail.usersSplit", { plan: formatNumber(planUsers), extra: formatNumber(extraUsers) })
                : undefined
            }
          />
          {data.purchased_volume ? (
            <Stat
              label={t("reseller.detail.purchasedVolume")}
              value={`${formatNumber(data.purchased_volume)} ${account.pricing_mode === "per_tb" ? t("reseller.tb") : t("reseller.gb")}`}
            />
          ) : null}
        </div>
      </Card>

      {/* Wallet */}
      {isPayg && (
        <Card className="p-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label={t("reseller.detail.balance")} value={formatToman(data.balance ?? 0)} />
            <Stat
              label={t("reseller.detail.rate")}
              value={t(account.pricing_mode === "hourly" ? "reseller.perActiveHour" : "reseller.perGbUsed", {
                amount: formatToman(data.rate),
              })}
            />
            <Stat label={t("reseller.detail.billedTotal")} value={formatToman(data.billed_total ?? 0)} />
            <div>
              <p className="text-[11px] text-muted">{t("reseller.runway")}</p>
              <div className="mt-1">
                <Badge tone={runwayTone(data.runway_hours, 24)}>{formatRunway(t, data.runway_hours)}</Badge>
              </div>
            </div>
          </div>
          <Link
            to="/balance"
            className="mt-3 flex h-10 items-center justify-center rounded-md border border-primary/30 bg-primary/5 text-sm font-semibold text-primary"
          >
            {t("reseller.detail.topUp")}
          </Link>
        </Card>
      )}

      {/* Credentials */}
      {actions.has("credentials") && (
        <Card className="space-y-2 p-4">
          <h3 className="mb-1 text-sm font-bold text-text">{t("reseller.detail.credentials")}</h3>
          {data.panel_url && data.panel_url !== "—" && <CopyField label={t("reseller.panelUrl")} value={data.panel_url} />}
          <CopyField label={t("reseller.buy.username")} value={account.username} />
          {password !== null ? (
            <CopyField label={t("reseller.password")} value={password} />
          ) : (
            <button
              type="button"
              onClick={revealPassword}
              disabled={reveal.isPending}
              className="flex w-full items-center gap-3 rounded-md border border-dashed border-border px-3 py-2.5 text-start hover:border-primary/40"
            >
              <div className="min-w-0 flex-1">
                <p className="text-[10.5px] text-muted">{t("reseller.password")}</p>
                <p className="font-mono text-[13px] tracking-widest text-text">••••••••</p>
              </div>
              <span className="flex items-center gap-1 text-xs font-semibold text-primary">
                <Eye size={14} />
                {t("reseller.detail.tapToShow")}
              </span>
            </button>
          )}
        </Card>
      )}

      {/* Actions */}
      {actions.size > 0 && (
        <div className="grid grid-cols-3 gap-2.5 sm:grid-cols-4">
          {actions.has("renew") && (
            <ActionTile icon={RefreshCw} label={t("reseller.detail.renew")} tone="success" onClick={() => setSheet("renew")} />
          )}
          {actions.has("extra_days") && (
            <ActionTile icon={CalendarPlus} label={t("reseller.detail.extraDays")} onClick={() => setSheet("extra_days")} />
          )}
          {actions.has("extra_volume") && (
            <ActionTile
              icon={HardDriveDownload}
              label={t("reseller.detail.extraVolume")}
              onClick={() => setSheet("extra_volume")}
            />
          )}
          {actions.has("buy_user_capacity") && (
            <ActionTile
              icon={UserPlus}
              label={t("reseller.detail.extraUsers")}
              onClick={() => setSheet("buy_user_capacity")}
            />
          )}
          {actions.has("usage_cap") && (
            <ActionTile icon={Gauge} label={t("reseller.detail.usageCap")} tone="warning" onClick={() => setSheet("cap")} />
          )}
          {actions.has("change_password") && (
            <ActionTile icon={KeyRound} label={t("reseller.detail.changePassword")} onClick={() => setSheet("password")} />
          )}
          {(actions.has("pause") || actions.has("resume")) && (
            <ActionTile
              icon={actions.has("pause") ? Pause : Play}
              label={t(actions.has("pause") ? "reseller.detail.pause" : "reseller.detail.resume")}
              tone={actions.has("pause") ? "warning" : "success"}
              onClick={() => setSheet("status")}
            />
          )}
          {actions.has("delete") && (
            <ActionTile icon={Trash2} label={t("reseller.detail.delete")} tone="danger" onClick={() => setSheet("delete")} />
          )}
        </div>
      )}

      {/* Plan rules */}
      {data.plan && (
        <Card className="space-y-3 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-bold text-text">{t("reseller.detail.planRules")}</h3>
            <ResellerModeBadge mode={data.plan.pricing_mode} />
          </div>
          {data.plan.name && <p className="text-xs text-muted">{data.plan.name}</p>}
          <ResellerPlanFeatureList plan={accountPlan ?? data.plan} showMinWallet={false} />
          <ResellerPlanGuide
            plan={accountPlan ?? data.plan}
            graceDays={data.grace_days ?? 0}
            minWallet={data.min_wallet_balance ?? 0}
            showMinWallet={false}
          />
        </Card>
      )}

      <History code={account.code} showUsage={actions.has("usage_report")} />

      {/* Sheets */}
      <Sheet open={sheet === "password"} onClose={() => setSheet(null)} title={t("reseller.detail.changePassword")}>
        <p className="text-sm leading-7 text-muted">{t("reseller.detail.changePasswordNote")}</p>
        <Button
          className="mt-4"
          fullWidth
          loading={reset.isPending}
          onClick={() =>
            reset.mutate(
              { code: account.code },
              {
                onSuccess: (res) => {
                  setPassword(res.password ?? "");
                  done(res.message);
                },
                onError: fail,
              }
            )
          }
        >
          {t("reseller.detail.changePasswordConfirm")}
        </Button>
      </Sheet>

      <Sheet
        open={sheet === "status"}
        onClose={() => setSheet(null)}
        title={t(actions.has("pause") ? "reseller.detail.pause" : "reseller.detail.resume")}
      >
        <p className="text-sm leading-7 text-muted">
          {t(actions.has("pause") ? "reseller.detail.pauseNote" : "reseller.detail.resumeNote")}
        </p>
        <Button
          className="mt-4"
          fullWidth
          variant={actions.has("pause") ? "danger" : "primary"}
          loading={pause.isPending || resume.isPending}
          onClick={() =>
            (actions.has("pause") ? pause : resume).mutate(
              { code: account.code },
              { onSuccess: (res) => done(res.message), onError: fail }
            )
          }
        >
          {t("reseller.detail.confirm")}
        </Button>
      </Sheet>

      <Sheet open={sheet === "delete"} onClose={() => setSheet(null)} title={t("reseller.detail.delete")}>
        <p className="rounded-md border border-danger/25 bg-danger/5 px-4 py-3 text-sm leading-7 text-danger">
          {t("reseller.detail.deleteNote", { name: account.username })}
        </p>
        <Button
          className="mt-4"
          fullWidth
          variant="danger"
          loading={remove.isPending}
          onClick={() =>
            remove.mutate(
              { code: account.code },
              {
                onSuccess: (res) => {
                  done(res.message);
                  navigate("/services?tab=reseller", { replace: true });
                },
                onError: fail,
              }
            )
          }
        >
          {t("reseller.detail.deleteConfirm")}
        </Button>
      </Sheet>

      {sheet === "renew" && <RenewSheet data={data} onClose={() => setSheet(null)} onDone={done} />}
      {sheet === "cap" && <UsageCapSheet data={data} onClose={() => setSheet(null)} onDone={done} onError={fail} />}
      {(sheet === "extra_days" || sheet === "extra_volume" || sheet === "buy_user_capacity") && (
        <AddonSheet key={sheet} addon={sheet} data={data} onClose={() => setSheet(null)} onDone={done} />
      )}
    </motion.div>
  );
}

interface SheetProps {
  data: WebAppResellerAccountResponse;
  onClose: () => void;
  onDone: (message?: string | null) => void;
}

function InlineError({ message }: { message: string }) {
  return (
    <p role="alert" className="rounded-md border border-danger/25 bg-danger/5 px-3.5 py-2.5 text-xs leading-6 text-danger">
      {message}
    </p>
  );
}

/** One "before → after" line of a paid action's preview. */
function ChangeRow({ label, before, after, changed = true }: { label: string; before: ReactNode; after: ReactNode; changed?: boolean }) {
  const { i18n } = useTranslation();
  const Arrow = i18n.dir() === "rtl" ? ArrowLeft : ArrowRight;
  return (
    <div className="flex items-center justify-between gap-3 text-[13px]">
      <span className="shrink-0 text-muted">{label}</span>
      <span className="flex min-w-0 flex-wrap items-center justify-end gap-1.5 text-end">
        <span className={changed ? "text-muted" : "font-semibold text-text"}>{before}</span>
        {changed && (
          <>
            <Arrow size={13} className="shrink-0 text-muted" aria-hidden />
            <span className="font-bold text-success">{after}</span>
          </>
        )}
      </span>
    </div>
  );
}

function ChangeCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="space-y-2 rounded-md border border-border p-3">
      <p className="text-xs font-bold text-text">{title}</p>
      {children}
    </div>
  );
}

function PriceSummary({
  final,
  base,
  unit,
  balance,
  balanceAfter,
  canPay,
}: {
  final: number;
  base?: number;
  unit?: string;
  balance: number;
  balanceAfter: number;
  canPay: boolean;
}) {
  const { t } = useTranslation();
  return (
    <div className="space-y-2 rounded-md bg-surface-2 p-3 text-sm">
      {unit && (
        <div className="flex justify-between gap-3">
          <span className="text-muted">{t("reseller.addon.unitPrice")}</span>
          <span className="text-text">{unit}</span>
        </div>
      )}
      {base != null && base !== final && (
        <div className="flex justify-between gap-3">
          <span className="text-muted">{t("buy.basePrice")}</span>
          <span className="text-muted line-through">{formatToman(base)}</span>
        </div>
      )}
      <div className="flex justify-between gap-3">
        <span className="text-muted">{t("reseller.addon.total")}</span>
        <span className="font-extrabold text-primary">{formatToman(final)}</span>
      </div>
      <div className="flex justify-between gap-3">
        <span className="text-muted">{t("buy.currentBalance")}</span>
        <span className="text-text">{formatToman(balance)}</span>
      </div>
      <div className="flex justify-between gap-3">
        <span className="text-muted">{t("buy.balanceAfter")}</span>
        <span className={canPay ? "font-semibold text-success" : "font-semibold text-danger"}>
          {formatToman(balanceAfter)}
        </span>
      </div>
      {!canPay && (
        <Link to="/balance" className="block pt-1 text-center text-xs font-semibold text-primary">
          {t("reseller.buy.topUp")}
        </Link>
      )}
    </div>
  );
}

function expiryValue(t: TFunction, timestamp: number | null | undefined): string {
  return timestamp ? formatUnixDate(timestamp) : t("reseller.noExpiry");
}

function daysLeftValue(t: TFunction, timestamp: number | null | undefined): string {
  const days = daysUntil(timestamp);
  if (days === null) return t("reseller.noExpiry");
  return days > 0 ? t("renewFlow.days", { count: formatNumber(days) }) : t("reseller.detail.expiredValue");
}

function volumeValue(t: TFunction, bytes: number): string {
  return bytes > 0 ? formatBytes(bytes) : t("reseller.detail.unlimitedVolume");
}

function RenewSheet({ data, onClose, onDone }: SheetProps) {
  const { t } = useTranslation();
  const code = data.account!.code;
  // The server only ever offers the account's own plan.
  const plan = data.renew_plans[0] ?? null;
  const [discountDraft, setDiscountDraft] = useState("");
  const [discount, setDiscount] = useState("");
  const [preview, setPreview] = useState<WebAppResellerRenewPreviewResponse | null>(null);
  const [error, setError] = useState("");
  const previewCall = useResellerMutation(resellerApi.previewRenew, { refresh: false });
  const confirm = useResellerMutation(resellerApi.confirmRenew);

  const runPreview = (code_: string) => {
    if (!plan) return;
    setError("");
    previewCall.mutate(
      { code, plan_id: plan.id, discount_code: code_.trim() || null },
      {
        onSuccess: (res) => {
          setPreview(res);
          setDiscount(code_.trim());
        },
        onError: (err) => setError((err as Error).message),
      }
    );
  };

  // Price the renewal as soon as the sheet opens.
  useEffect(() => {
    runPreview("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const submit = () => {
    if (!plan) return;
    setError("");
    confirm.mutate(
      { code, plan_id: plan.id, discount_code: discount || null },
      { onSuccess: (res) => onDone(res.message), onError: (err) => setError((err as Error).message) }
    );
  };

  const addsVolume = preview != null && (preview.data_limit_after ?? 0) !== (preview.data_limit_before ?? 0);

  return (
    <Sheet open onClose={onClose} title={t("reseller.detail.renew")}>
      {!plan ? (
        <p className="py-4 text-center text-sm text-muted">{t("reseller.renew.noPlan")}</p>
      ) : (
        <div className="space-y-3">
          <div className="rounded-lg border-[1.5px] border-primary bg-primary/6 p-3.5">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 space-y-1.5">
                <p className="text-base font-extrabold text-text">
                  {plan.name || resellerModeLabel(t, plan.pricing_mode || data.account!.pricing_mode)}
                </p>
                <ResellerModeBadge mode={plan.pricing_mode || data.account!.pricing_mode} />
              </div>
              <p className="shrink-0 text-sm font-extrabold text-text">{formatToman(plan.price)}</p>
            </div>
            <p className="mt-2 text-xs text-muted">
              {[
                plan.data_limit_bytes ? t("reseller.renew.addsVolume", { volume: formatBytes(plan.data_limit_bytes) }) : null,
                plan.duration_days
                  ? t("reseller.renew.addsDays", { count: formatNumber(plan.duration_days) })
                  : null,
              ]
                .filter(Boolean)
                .join(" · ")}
            </p>
          </div>
          <p className="text-xs leading-6 text-muted">{t("reseller.renew.ownPlanOnly")}</p>
          {plan.enabled === false && (
            <p className="rounded-md border border-border bg-surface-2 px-3.5 py-2.5 text-xs leading-6 text-muted">
              {t("reseller.renew.disabledPlan")}
            </p>
          )}

          <div className="flex items-start gap-2">
            <Input
              value={discountDraft}
              onChange={(event) => setDiscountDraft(event.target.value)}
              placeholder={t("buy.discountCodePlaceholder")}
              ltr
            />
            <Button
              variant="secondary"
              className="h-10 shrink-0"
              loading={previewCall.isPending}
              disabled={discountDraft.trim() === discount}
              onClick={() => runPreview(discountDraft)}
            >
              {t("reseller.buy.apply")}
            </Button>
          </div>
          {discount && preview && preview.discount_percent > 0 && (
            <p className="text-xs font-semibold text-success">
              {t("reseller.buy.discountApplied", { percent: formatNumber(preview.discount_percent) })}
            </p>
          )}

          {preview && (
            <>
              <ChangeCard title={t("reseller.addon.changes")}>
                <ChangeRow
                  label={t("reseller.addon.rowExpiry")}
                  before={expiryValue(t, preview.expiry_before)}
                  after={expiryValue(t, preview.expiry_after)}
                  changed={preview.expiry_after !== preview.expiry_before}
                />
                <ChangeRow
                  label={t("reseller.addon.rowDaysLeft")}
                  before={daysLeftValue(t, preview.expiry_before)}
                  after={daysLeftValue(t, preview.expiry_after)}
                  changed={preview.expiry_after !== preview.expiry_before}
                />
                <ChangeRow
                  label={t("reseller.addon.rowVolume")}
                  before={volumeValue(t, preview.data_limit_before ?? 0)}
                  after={volumeValue(t, preview.data_limit_after ?? 0)}
                  changed={addsVolume}
                />
                <ChangeRow
                  label={t("reseller.addon.rowUsers")}
                  before={
                    preview.max_users
                      ? `${formatNumber(preview.max_users)} · ${t("reseller.renew.usersUnchanged")}`
                      : `${t("reseller.unlimitedUsers")} · ${t("reseller.renew.usersUnchanged")}`
                  }
                  after={null}
                  changed={false}
                />
              </ChangeCard>
              <p className="text-xs leading-6 text-muted">{t("reseller.renew.nothingResets")}</p>
              <PriceSummary
                final={preview.final_price}
                base={preview.base_price}
                balance={preview.balance}
                balanceAfter={preview.balance_after ?? preview.balance - preview.final_price}
                canPay={preview.can_pay}
              />
            </>
          )}
          {error && <InlineError message={error} />}
          <Button fullWidth loading={confirm.isPending} disabled={!preview?.can_pay || previewCall.isPending} onClick={submit}>
            {previewCall.isPending && !preview ? t("reseller.addon.calculating") : t("reseller.detail.renewConfirm")}
          </Button>
        </div>
      )}
    </Sheet>
  );
}

function UsageCapSheet({ data, onClose, onDone, onError }: SheetProps & { onError: (err: unknown) => void }) {
  const { t } = useTranslation();
  const code = data.account!.code;
  const [value, setValue] = useState(data.usage_cap_bytes ? String(+(data.usage_cap_bytes / GB).toFixed(2)) : "");
  const save = useResellerMutation(resellerApi.setUsageCap);
  const submit = (gb: number | null) =>
    save.mutate({ code, usage_cap_gb: gb }, { onSuccess: (res) => onDone(res.message), onError });

  return (
    <Sheet open onClose={onClose} title={t("reseller.detail.usageCap")}>
      <p className="mb-3 text-sm leading-7 text-muted">{t("reseller.detail.capNote")}</p>
      <Input
        label={t("reseller.detail.capGb")}
        inputMode="decimal"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        ltr
      />
      <div className="mt-4 grid grid-cols-2 gap-2">
        {data.usage_cap_bytes ? (
          <Button variant="secondary" loading={save.isPending} onClick={() => submit(null)}>
            {t("reseller.detail.removeCap")}
          </Button>
        ) : (
          <span />
        )}
        <Button loading={save.isPending} disabled={!(Number(value) > 0)} onClick={() => submit(Number(value))}>
          {t("reseller.detail.saveCap")}
        </Button>
      </div>
    </Sheet>
  );
}

const ADDON_TEXT: Record<ResellerAddonKind, { title: string; quantity: string; unit: string; preset: string }> = {
  extra_days: {
    title: "reseller.detail.extraDays",
    quantity: "reseller.addon.quantityDays",
    unit: "reseller.plan.perDay",
    preset: "reseller.addon.presetDays",
  },
  extra_volume: {
    title: "reseller.detail.extraVolume",
    quantity: "reseller.addon.quantityGb",
    unit: "reseller.plan.perGb",
    preset: "reseller.addon.presetGb",
  },
  buy_user_capacity: {
    title: "reseller.detail.extraUsers",
    quantity: "reseller.addon.quantityUsers",
    unit: "reseller.plan.perUser",
    preset: "reseller.addon.presetUsers",
  },
};

/** Extra days, extra volume or extra users: quantity, live before → after preview, price and confirm. */
function AddonSheet({ addon, data, onClose, onDone }: SheetProps & { addon: ResellerAddonKind }) {
  const { t } = useTranslation();
  const code = data.account!.code;
  const text = ADDON_TEXT[addon];
  const presets = data.addon_presets?.[addon] ?? (addon === "buy_user_capacity" ? data.capacity_presets : []);
  const max = data.addon_max_quantity?.[addon] ?? ADDON_FALLBACK_MAX[addon];
  const renewable = data.plan ? resolvePlanFeatures(data.plan).renewable : false;

  const [quantity, setQuantity] = useState<number>(presets[0] ?? 1);
  const [custom, setCustom] = useState("");
  const [preview, setPreview] = useState<WebAppResellerAddonPreviewResponse | null>(null);
  const [previewError, setPreviewError] = useState("");
  const [confirmError, setConfirmError] = useState("");
  const previewCall = useResellerMutation(resellerApi.previewAddon, { refresh: false });
  const confirm = useResellerMutation(resellerApi.confirmAddon);
  const requestId = useRef(0);

  const chosen = custom ? Number(custom) || 0 : quantity;
  const tooMany = chosen > max;
  const valid = Number.isInteger(chosen) && chosen >= 1 && !tooMany;
  // The preview on screen must match what is about to be bought.
  const current = preview != null && preview.quantity === chosen ? preview : null;

  // Live preview: re-price shortly after the quantity settles; stale answers are dropped.
  useEffect(() => {
    setConfirmError("");
    if (!valid) {
      setPreview(null);
      setPreviewError(tooMany ? t("reseller.addon.maxHint", { max: formatNumber(max) }) : "");
      return;
    }
    const id = ++requestId.current;
    const timer = window.setTimeout(() => {
      previewCall.mutate(
        { code, addon, quantity: chosen },
        {
          onSuccess: (res) => {
            if (id !== requestId.current) return;
            setPreview(res);
            setPreviewError("");
          },
          onError: (err) => {
            if (id !== requestId.current) return;
            setPreview(null);
            setPreviewError((err as Error).message);
          },
        }
      );
    }, 300);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chosen, valid]);

  const submit = () => {
    if (!current) return;
    setConfirmError("");
    confirm.mutate(
      { code, addon, quantity: current.quantity },
      { onSuccess: (res) => onDone(res.message), onError: (err) => setConfirmError((err as Error).message) }
    );
  };

  const note =
    addon === "extra_days"
      ? t("reseller.addon.noteDays")
      : addon === "extra_volume"
        ? t("reseller.addon.noteVolume")
        : t(renewable ? "reseller.addon.noteUsersRenewable" : "reseller.addon.noteUsers");

  const unitPrice =
    current?.unit_price ??
    (addon === "extra_days"
      ? data.features?.extra_day_price
      : addon === "extra_volume"
        ? data.features?.extra_gb_price
        : data.features?.extra_user_price || data.capacity_price_per_user);

  return (
    <Sheet open onClose={onClose} title={t(text.title)}>
      <div className="space-y-3">
        <p className="text-sm leading-7 text-muted">
          {unitPrice ? `${t(text.unit, { price: formatToman(unitPrice) })} · ` : ""}
          {note}
        </p>

        {presets.length > 0 && (
          <div className="grid grid-cols-3 gap-2">
            {presets.map((preset) => (
              <button
                key={preset}
                type="button"
                onClick={() => {
                  setQuantity(preset);
                  setCustom("");
                }}
                className={`rounded-md border py-2.5 text-center text-sm font-bold transition-colors ${
                  !custom && quantity === preset ? "border-primary bg-primary/10 text-primary" : "border-border text-text"
                }`}
              >
                {t(text.preset, { count: formatNumber(preset) })}
              </button>
            ))}
          </div>
        )}
        <Input
          label={t(presets.length ? "reseller.addon.custom" : text.quantity)}
          inputMode="numeric"
          value={custom}
          placeholder={t(text.quantity)}
          onChange={(event) => setCustom(event.target.value.replace(/\D/g, "").slice(0, 7))}
          ltr
        />

        {current && (
          <>
            <ChangeCard title={t("reseller.addon.changes")}>
              {addon === "extra_days" && (
                <>
                  <ChangeRow
                    label={t("reseller.addon.rowExpiry")}
                    before={expiryValue(t, current.before)}
                    after={expiryValue(t, current.after)}
                  />
                  <ChangeRow
                    label={t("reseller.addon.rowDaysLeft")}
                    before={daysLeftValue(t, current.before)}
                    after={daysLeftValue(t, current.after)}
                  />
                </>
              )}
              {addon === "extra_volume" && (
                <>
                  <ChangeRow
                    label={t("reseller.addon.rowVolume")}
                    before={formatBytes(current.before)}
                    after={formatBytes(current.after)}
                  />
                  {data.live && (
                    <ChangeRow
                      label={t("reseller.detail.remaining")}
                      before={formatBytes(Math.max(0, current.before - data.used_traffic_bytes), 2)}
                      after={formatBytes(Math.max(0, current.after - data.used_traffic_bytes), 2)}
                    />
                  )}
                </>
              )}
              {addon === "buy_user_capacity" && (
                <ChangeRow
                  label={t("reseller.addon.rowUsers")}
                  before={formatNumber(current.before)}
                  after={formatNumber(current.after)}
                />
              )}
            </ChangeCard>
            <PriceSummary
              final={current.total}
              unit={t(text.unit, { price: formatToman(current.unit_price) })}
              balance={current.balance}
              balanceAfter={current.balance_after}
              canPay={current.can_pay}
            />
          </>
        )}
        {previewError && <InlineError message={previewError} />}
        {confirmError && <InlineError message={confirmError} />}

        <Button fullWidth loading={confirm.isPending} disabled={!current?.can_pay || previewCall.isPending} onClick={submit}>
          {current || !valid ? t("reseller.addon.confirm") : t("reseller.addon.calculating")}
        </Button>
      </div>
    </Sheet>
  );
}
