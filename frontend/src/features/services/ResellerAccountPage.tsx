import { useState } from "react";
import type { ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Eye,
  Gauge,
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
import { PageHeader } from "../../components/layout/PageHeader";
import {
  Badge,
  Button,
  Card,
  CopyField,
  IconBadge,
  Input,
  PlanOption,
  Sheet,
  SkeletonCard,
} from "../../components/ui";
import { ErrorState } from "../../components/ui/EmptyState";
import { ChargeItem } from "../../components/ChargeItem";
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
  ResellerEventItem,
  WebAppResellerAccountResponse,
  WebAppResellerCapacityPreviewResponse,
  WebAppResellerRenewPreviewResponse,
} from "../../types/webapp";

type SheetKind = "password" | "status" | "renew" | "cap" | "capacity" | "delete" | null;
const GB = 1024 ** 3;

const DOT: Record<string, string> = {
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  primary: "bg-primary",
  muted: "bg-muted",
};

function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="min-w-0">
      <p className="truncate text-[11px] text-muted">{label}</p>
      <p className="mt-0.5 truncate text-sm font-bold text-text">{value}</p>
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
        <div className="grid grid-cols-2 gap-3 border-t border-border pt-3 sm:grid-cols-3">
          <Stat
            label={t("reseller.detail.users")}
            value={`${formatNumber(data.total_users)} / ${account.max_users ? formatNumber(account.max_users) : "∞"}`}
          />
          <Stat
            label={t("reseller.detail.expiry")}
            value={account.expiration_timestamp ? formatUnixDate(account.expiration_timestamp) : t("reseller.noExpiry")}
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
              value={t(account.pricing_mode === "hourly" ? "reseller.perHour" : "reseller.perGbUsed", {
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
        <div className="grid grid-cols-3 gap-2.5 sm:grid-cols-6">
          {actions.has("renew") && (
            <ActionTile icon={RefreshCw} label={t("reseller.detail.renew")} tone="success" onClick={() => setSheet("renew")} />
          )}
          {actions.has("buy_user_capacity") && (
            <ActionTile icon={UserPlus} label={t("reseller.detail.capacity")} onClick={() => setSheet("capacity")} />
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

      {sheet === "renew" && <RenewSheet data={data} onClose={() => setSheet(null)} onDone={done} onError={fail} />}
      {sheet === "cap" && <UsageCapSheet data={data} onClose={() => setSheet(null)} onDone={done} onError={fail} />}
      {sheet === "capacity" && (
        <CapacitySheet data={data} onClose={() => setSheet(null)} onDone={done} onError={fail} />
      )}
    </motion.div>
  );
}

interface SheetProps {
  data: WebAppResellerAccountResponse;
  onClose: () => void;
  onDone: (message?: string | null) => void;
  onError: (err: unknown) => void;
}

function PriceSummary({ final, base, balance, canPay }: { final: number; base?: number; balance: number; canPay: boolean }) {
  const { t } = useTranslation();
  return (
    <div className="space-y-2 rounded-md bg-surface-2 p-3 text-sm">
      {base != null && base !== final && (
        <div className="flex justify-between">
          <span className="text-muted">{t("buy.basePrice")}</span>
          <span className="text-muted line-through">{formatToman(base)}</span>
        </div>
      )}
      <div className="flex justify-between">
        <span className="text-muted">{t("buy.finalPrice")}</span>
        <span className="font-extrabold text-primary">{formatToman(final)}</span>
      </div>
      <div className="flex justify-between">
        <span className="text-muted">{t("buy.currentBalance")}</span>
        <span className={canPay ? "text-text" : "font-semibold text-danger"}>{formatToman(balance)}</span>
      </div>
      {!canPay && (
        <Link to="/balance" className="block pt-1 text-center text-xs font-semibold text-primary">
          {t("reseller.buy.topUp")}
        </Link>
      )}
    </div>
  );
}

function RenewSheet({ data, onClose, onDone, onError }: SheetProps) {
  const { t } = useTranslation();
  const code = data.account!.code;
  const [planId, setPlanId] = useState<number | null>(data.renew_plans[0]?.id ?? null);
  const [discount, setDiscount] = useState("");
  const [preview, setPreview] = useState<WebAppResellerRenewPreviewResponse | null>(null);
  const previewCall = useResellerMutation(resellerApi.previewRenew, { refresh: false });
  const confirm = useResellerMutation(resellerApi.confirmRenew);

  const runPreview = (nextPlan: number | null, code_: string) => {
    if (!nextPlan) return;
    previewCall.mutate(
      { code, plan_id: nextPlan, discount_code: code_.trim() || null },
      { onSuccess: setPreview, onError: (err) => (setPreview(null), onError(err)) }
    );
  };

  return (
    <Sheet open onClose={onClose} title={t("reseller.detail.renew")}>
      {data.renew_plans.length === 0 ? (
        <p className="py-4 text-center text-sm text-muted">{t("reseller.detail.noRenewPlans")}</p>
      ) : (
        <div className="space-y-3">
          <div role="radiogroup" className="space-y-2">
            {data.renew_plans.map((plan) => (
              <PlanOption
                key={plan.id}
                title={plan.name || t("reseller.mode.fixed")}
                subtitle={[
                  plan.data_limit_bytes ? formatBytes(plan.data_limit_bytes) : null,
                  plan.duration_days ? t("renewFlow.days", { count: formatNumber(plan.duration_days) }) : null,
                ]
                  .filter(Boolean)
                  .join(" · ")}
                price={formatToman(plan.price)}
                selected={planId === plan.id}
                onSelect={() => {
                  setPlanId(plan.id);
                  setPreview(null);
                }}
              />
            ))}
          </div>
          <div className="flex items-start gap-2">
            <Input
              value={discount}
              onChange={(event) => setDiscount(event.target.value)}
              placeholder={t("buy.discountCodePlaceholder")}
              ltr
            />
            <Button
              variant="secondary"
              className="h-10 shrink-0"
              loading={previewCall.isPending}
              disabled={!planId}
              onClick={() => runPreview(planId, discount)}
            >
              {t("reseller.detail.calculate")}
            </Button>
          </div>
          {preview && (
            <PriceSummary
              final={preview.final_price}
              base={preview.base_price}
              balance={preview.balance}
              canPay={preview.can_pay}
            />
          )}
          <Button
            fullWidth
            loading={confirm.isPending}
            disabled={!preview?.can_pay}
            onClick={() =>
              planId &&
              confirm.mutate(
                { code, plan_id: planId, discount_code: discount.trim() || null },
                { onSuccess: (res) => onDone(res.message), onError }
              )
            }
          >
            {preview ? t("reseller.detail.renewConfirm") : t("reseller.detail.calculateFirst")}
          </Button>
        </div>
      )}
    </Sheet>
  );
}

function UsageCapSheet({ data, onClose, onDone, onError }: SheetProps) {
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

function CapacitySheet({ data, onClose, onDone, onError }: SheetProps) {
  const { t } = useTranslation();
  const code = data.account!.code;
  const [quantity, setQuantity] = useState(data.capacity_presets[0] ?? 5);
  const [custom, setCustom] = useState("");
  const [preview, setPreview] = useState<WebAppResellerCapacityPreviewResponse | null>(null);
  const previewCall = useResellerMutation(resellerApi.previewCapacity, { refresh: false });
  const confirm = useResellerMutation(resellerApi.confirmCapacity);
  const chosen = custom ? Number(custom) || 0 : quantity;

  const runPreview = () =>
    previewCall.mutate({ code, quantity: chosen }, { onSuccess: setPreview, onError: (err) => (setPreview(null), onError(err)) });

  return (
    <Sheet open onClose={onClose} title={t("reseller.detail.capacity")}>
      <p className="mb-3 text-sm text-muted">
        {t("reseller.detail.capacityNote", { price: formatToman(data.capacity_price_per_user) })}
      </p>
      <div className="mb-3 grid grid-cols-3 gap-2">
        {data.capacity_presets.map((preset) => (
          <button
            key={preset}
            type="button"
            onClick={() => {
              setQuantity(preset);
              setCustom("");
              setPreview(null);
            }}
            className={`rounded-md border py-2.5 text-center text-sm font-bold transition-colors ${
              !custom && quantity === preset ? "border-primary bg-primary/10 text-primary" : "border-border text-text"
            }`}
          >
            +{formatNumber(preset)}
          </button>
        ))}
      </div>
      <div className="flex items-end gap-2">
        <Input
          label={t("reseller.detail.customQuantity")}
          inputMode="numeric"
          value={custom}
          onChange={(event) => {
            setCustom(event.target.value.replace(/\D/g, ""));
            setPreview(null);
          }}
          ltr
        />
        <Button variant="secondary" className="h-10 shrink-0" loading={previewCall.isPending} disabled={chosen <= 0} onClick={runPreview}>
          {t("reseller.detail.calculate")}
        </Button>
      </div>
      {preview && (
        <div className="mt-3 space-y-2">
          <p className="text-center text-xs text-muted">
            {t("reseller.detail.limitChange", {
              before: formatNumber(preview.limit_before),
              after: formatNumber(preview.limit_after),
            })}
          </p>
          <PriceSummary final={preview.total_price} balance={preview.balance} canPay={preview.can_pay} />
        </div>
      )}
      <Button
        className="mt-4"
        fullWidth
        loading={confirm.isPending}
        disabled={!preview?.can_pay}
        onClick={() => confirm.mutate({ code, quantity: chosen }, { onSuccess: (res) => onDone(res.message), onError })}
      >
        {preview ? t("reseller.detail.buyCapacity") : t("reseller.detail.calculateFirst")}
      </Button>
    </Sheet>
  );
}
