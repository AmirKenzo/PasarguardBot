import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, animate, m } from "framer-motion";
import { Link } from "react-router-dom";
import QRCode from "qrcode";
import {
  AlertTriangle,
  ArrowUpDown,
  CalendarPlus,
  Power,
  PowerOff,
  QrCode,
  SlidersHorizontal,
  Clock,
  AtSign,
  CalendarDays,
  Dices,
  HardDrive,
  Infinity as InfinityIcon,
  Minus,
  StickyNote,
  UserPlus,
  BarChart3,
  Check,
  Layers,
  Ban,
  Bot,
  CircleCheck,
  Hourglass,
  Link2,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  Trash2,
  Users,
  Wallet,
  Wifi,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge, Button, Card, CopyField, Pagination, ProgressRing, Sheet, SkeletonCard, Tabs } from "../../components/ui";
import { EmptyState, ErrorState } from "../../components/ui/EmptyState";
import { useToast } from "../../components/ui/Toast";
import { botResellerApi } from "../../api/webapp";
import { useTelegram } from "../../hooks/useTelegram";
import { clampPercent, formatBytes, formatNumber, formatRelativeTime, formatToman, formatUnixDate } from "../../lib/format";
import {
  useBotResellerMutation,
  useBotResellerState,
  useBotResellerUsage,
  useBotResellerUser,
  useBotResellerUsers,
} from "../../queries/useBotReseller";
import type { BotResellerServiceItem, BotResellerStateResponse, BotResellerUsageRow, BotResellerUserItem } from "../../types/webapp";

type Tab = "users" | "usage";
const NAME_RE = /^[a-z0-9][a-z0-9_]{1,20}[a-z0-9]$/;
const ONLINE_WINDOW_S = 180;
const PAGE_SIZE = 20;
const SOON_DAYS = 3;
const SOON_PERCENT = 85;
const GB = 1024 ** 3;

export default function BotResellerPage() {
  const { t } = useTranslation();
  const state = useBotResellerState();
  const [tab, setTab] = useState<Tab>("users");
  const [creating, setCreating] = useState(false);
  const [openUser, setOpenUser] = useState<number | null>(null);

  if (state.isLoading) {
    return (
      <div className="space-y-3">
        <PageHeader title={t("botReseller.title")} back="/services" />
        <SkeletonCard />
        <SkeletonCard />
      </div>
    );
  }
  if (state.isError || !state.data) {
    return (
      <div className="space-y-3">
        <PageHeader title={t("botReseller.title")} back="/services" />
        <ErrorState message={state.error?.message || t("apiErrors.unknownError")} onRetry={() => void state.refetch()} />
      </div>
    );
  }

  const data = state.data;
  if (!data.is_reseller) {
    return (
      <div className="space-y-3">
        <PageHeader title={t("botReseller.title")} back="/services" />
        <EmptyState
          icon={Bot}
          title={t("botReseller.notActive")}
          description={data.pending.length ? t("botReseller.pending", { services: data.pending.join("، ") }) : t("botReseller.notActiveHint")}
        />
      </div>
    );
  }

  const blocked = data.status === "frozen" || data.status === "suspended";

  return (
    <div className="space-y-4">
      <PageHeader title={t("botReseller.title")} subtitle={t("botReseller.subtitle")} back="/services" />
      <StatusBanner data={data} />
      <Tabs
        value={tab}
        onChange={(v) => setTab(v as Tab)}
        items={[
          { value: "users", label: t("botReseller.tabs.users"), icon: Users },
          { value: "usage", label: t("botReseller.tabs.usage"), icon: BarChart3 },
        ]}
      />

      {tab === "users" && <UsersTab onOpen={setOpenUser} onCreate={() => setCreating(true)} blocked={blocked} />}
      {tab === "usage" && <UsageTab data={data} />}

      <CreateUserSheet open={creating} onClose={() => setCreating(false)} services={data.services} prefix={data.username_prefix} suffix={data.username_suffix} />
      <UserSheet id={openUser} onClose={() => setOpenUser(null)} services={data.services} blocked={blocked} />
    </div>
  );
}

function StatusBanner({ data }: { data: BotResellerStateResponse }) {
  const { t } = useTranslation();
  if (data.status === "frozen") {
    return (
      <Card className="border-danger/30 bg-danger/10 p-3 text-sm text-danger">
        <p className="font-bold">{t("botReseller.frozenTitle")}</p>
        <p className="mt-1">{t("botReseller.frozenBody")}</p>
        <Link to="/balance" className="mt-2 inline-block font-bold underline">
          {t("botReseller.topUp")}
        </Link>
      </Card>
    );
  }
  if (data.status === "suspended") {
    return <Card className="border-warning/30 bg-warning/10 p-3 text-sm text-warning">{t("botReseller.suspended")}</Card>;
  }
  return null;
}

function LiveDot() {
  return (
    <span className="relative flex h-1.5 w-1.5">
      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-75" />
      <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-success" />
    </span>
  );
}

function LiveBalance({ value, className = "text-2xl" }: { value: number; className?: string }) {
  const [shown, setShown] = useState(value);
  const [drops, setDrops] = useState<{ key: number; amount: number }[]>([]);
  const last = useRef(value);
  const current = useRef(value);
  useEffect(() => {
    const diff = value - last.current;
    last.current = value;
    if (diff < 0) {
      const key = Date.now();
      setDrops((list) => [...list, { key, amount: -diff }]);
      window.setTimeout(() => setDrops((list) => list.filter((d) => d.key !== key)), 2400);
    }
    const controls = animate(current.current, value, {
      duration: 1.2,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (v) => {
        current.current = v;
        setShown(Math.round(v));
      },
    });
    return () => controls.stop();
  }, [value]);
  return (
    <div className="relative inline-flex items-center">
      <p className={`font-black tabular-nums ${className}`}>{formatToman(shown)}</p>
      <AnimatePresence>
        {drops.map((drop) => (
          <m.span
            key={drop.key}
            initial={{ opacity: 0, y: 0 }}
            animate={{ opacity: 1, y: -18 }}
            exit={{ opacity: 0, y: -30 }}
            transition={{ duration: 0.6 }}
            className="pointer-events-none absolute -top-2 start-full ms-2 whitespace-nowrap rounded-full bg-danger/15 px-2 py-0.5 text-xs font-black tabular-nums text-danger"
          >
            −{formatNumber(drop.amount)}
          </m.span>
        ))}
      </AnimatePresence>
    </div>
  );
}

function WalletCard({ data }: { data: BotResellerStateResponse }) {
  const { t } = useTranslation();
  const runway = data.runway_hours;
  const runwayPercent = runway == null ? 100 : Math.min(100, (runway / 72) * 100);
  const tone = runway != null && runway < 6 ? "bg-danger" : runway != null && runway < 24 ? "bg-warning" : "bg-success";

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="flex items-center gap-1.5 text-xs text-muted">
          <Wallet size={13} />
          {t("botReseller.balance")}
          <span className="inline-flex items-center gap-1 rounded-full bg-success/15 px-1.5 py-0.5 text-[10px] font-bold text-success">
            <LiveDot />
            {t("botReseller.live")}
          </span>
        </p>
        <Link to="/balance" className="shrink-0">
          <Button size="sm" variant="secondary">
            <Plus size={14} />
            {t("botReseller.topUp")}
          </Button>
        </Link>
      </div>
      <div className="mt-2">
        <LiveBalance value={data.balance} className="whitespace-nowrap text-2xl" />
      </div>
      <div className="mt-4">
        <div className="flex justify-between text-xs text-muted">
          <span>{t("botReseller.runwayLabel")}</span>
          <span>{runway != null ? t("botReseller.runwayShort", { hours: formatNumber(Math.round(runway)) }) : t("botReseller.noBurn")}</span>
        </div>
        <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-surface-2">
          <m.div className={`h-full rounded-full ${tone}`} initial={{ width: 0 }} animate={{ width: `${runwayPercent}%` }} transition={{ duration: 0.8 }} />
        </div>
      </div>
      <div className="mt-4 divide-y divide-border rounded-xl bg-surface-2/60 px-3">
        <StatLine label={t("botReseller.perHour")} value={formatToman(data.burn_per_hour)} />
        <StatLine label={t("botReseller.spent24h")} value={formatToman(data.usage_24h_amount)} />
        <StatLine label={t("botReseller.usage24h")} value={formatBytes(data.usage_24h_bytes, 1)} />
      </div>
    </Card>
  );
}

function StatLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2 text-xs">
      <span className="text-muted">{label}</span>
      <b className="whitespace-nowrap tabular-nums">{value}</b>
    </div>
  );
}

function ServiceCard({ service }: { service: BotResellerServiceItem }) {
  const { t } = useTranslation();
  const fill = service.max_users ? clampPercent(service.users, service.max_users) : 0;
  return (
    <Card className="p-3">
      <div className="flex items-center justify-between gap-2">
        <b className="text-sm">{service.name}</b>
        <Badge tone="primary">{t("botReseller.perGb", { price: formatNumber(service.price_per_gb) })}</Badge>
      </div>
      <div className="mt-2 flex justify-between text-xs text-muted">
        <span>
          {formatNumber(service.users)}
          {service.max_users ? ` / ${formatNumber(service.max_users)}` : ""} {t("botReseller.usersCount")}
        </span>
        <span>{formatBytes(service.usage_24h_bytes, 1)} / 24h</span>
      </div>
      {service.max_users > 0 && (
        <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-surface-2">
          <div className="h-full rounded-full bg-primary" style={{ width: `${fill}%` }} />
        </div>
      )}
    </Card>
  );
}

const CHARGES_PAGE_SIZE = 8;

function ChargesList({ rows, loading, error }: { rows?: BotResellerUsageRow[]; loading: boolean; error: string | null }) {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  if (loading) return <SkeletonCard />;
  if (error) return <ErrorState message={error} />;
  if (!rows?.length) return <EmptyState icon={RefreshCw} title={t("botReseller.noUsage")} />;
  const totalPages = Math.ceil(rows.length / CHARGES_PAGE_SIZE);
  const current = Math.min(page, totalPages);
  const shown = rows.slice((current - 1) * CHARGES_PAGE_SIZE, current * CHARGES_PAGE_SIZE);
  return (
    <div className="space-y-3">
    <Card className="divide-y divide-border">
      {shown.map((row) => (
        <div key={`${row.hour}-${row.service_id}`} className="flex items-center justify-between gap-3 px-3 py-2.5">
          <div className="min-w-0">
            <p className="truncate text-xs font-bold">{t("botReseller.usageRow", { time: formatUnixDate(row.hour) })}</p>
            <p className="text-xs text-muted">
              {row.service_name} · {formatBytes(row.bytes, 2)}
            </p>
          </div>
          <span className="shrink-0 whitespace-nowrap text-sm font-bold tabular-nums text-danger">−{formatToman(row.amount)}</span>
        </div>
      ))}
    </Card>
      {totalPages > 1 && (
        <div className="flex justify-center">
          <Pagination page={current} totalPages={totalPages} onChange={setPage} />
        </div>
      )}
    </div>
  );
}

type HourPoint = { hour: number; bytes: number; amount: number };

function HourlyChart({ hours }: { hours: HourPoint[] }) {
  const { t, i18n } = useTranslation();
  const [picked, setPicked] = useState<number | null>(null);
  const peak = Math.max(1, ...hours.map((h) => h.bytes));
  const index = picked ?? hours.length - 1;
  const point = hours[index];
  const clock = (ts: number) =>
    new Date(ts * 1000).toLocaleTimeString(i18n.language.startsWith("fa") ? "fa-IR" : "en-GB", { hour: "2-digit", minute: "2-digit", hour12: false });

  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-black">{t("botReseller.hourlyChart")}</p>
          <p className="mt-0.5 flex items-center gap-1 text-[11px] text-muted" dir="ltr">
            <Clock size={11} />
            {point ? `${clock(point.hour)} – ${clock(point.hour + 3600)}` : "—"}
          </p>
        </div>
        <div className="text-end">
          <p className="text-base font-black tabular-nums">{formatBytes(point?.bytes || 0, 2)}</p>
          <p className="text-[11px] font-bold tabular-nums text-danger">−{formatToman(point?.amount || 0)}</p>
        </div>
      </div>
      <div className="mt-3 flex h-28 items-end gap-[3px]" onPointerLeave={() => setPicked(null)}>
        {hours.map((h, i) => (
          <button
            key={h.hour}
            type="button"
            aria-label={`${clock(h.hour)} · ${formatBytes(h.bytes, 2)}`}
            onPointerEnter={() => setPicked(i)}
            onClick={() => setPicked(i)}
            className="flex h-full flex-1 items-end"
          >
            <m.span
              className={`block w-full rounded-t transition-colors ${i === index ? "bg-primary" : "bg-primary/35"}`}
              initial={{ height: 0 }}
              animate={{ height: `${Math.max(h.bytes ? 4 : 1, (h.bytes / peak) * 100)}%` }}
              transition={{ duration: 0.5, delay: i * 0.015 }}
            />
          </button>
        ))}
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-muted">
        <span>{t("botReseller.hoursAgo", { hours: formatNumber(24) })}</span>
        <span>{t("botReseller.now")}</span>
      </div>
    </Card>
  );
}

function UsageTab({ data }: { data: BotResellerStateResponse }) {
  const { t } = useTranslation();
  const usage = useBotResellerUsage(true);
  const users = useBotResellerUsers(true);
  const rows = usage.data?.rows || [];

  const summary = useMemo(() => {
    const since = Math.floor(Date.now() / 1000) - 86400;
    const byService = new Map<string, { bytes: number; amount: number }>();
    const byHour = new Map<number, { bytes: number; amount: number }>();
    let bytes = 0;
    let amount = 0;
    for (const row of rows) {
      if (row.hour < since) continue;
      bytes += row.bytes;
      amount += row.amount;
      const s = byService.get(row.service_name) || { bytes: 0, amount: 0 };
      byService.set(row.service_name, { bytes: s.bytes + row.bytes, amount: s.amount + row.amount });
      const h = byHour.get(row.hour) || { bytes: 0, amount: 0 };
      byHour.set(row.hour, { bytes: h.bytes + row.bytes, amount: h.amount + row.amount });
    }
    const hourStart = Math.floor(Date.now() / 3_600_000) * 3600;
    const hours = Array.from({ length: 24 }, (_, i) => {
      const hour = hourStart - (23 - i) * 3600;
      return { hour, bytes: byHour.get(hour)?.bytes || 0, amount: byHour.get(hour)?.amount || 0 };
    });
    return { bytes, amount, byService: [...byService.entries()].sort((a, b) => b[1].bytes - a[1].bytes), hours };
  }, [rows]);

  const top = useMemo(() => [...(users.data?.users || [])].sort((a, b) => b.used_bytes - a.used_bytes).slice(0, 5), [users.data]);

  if (usage.isLoading) return <SkeletonCard />;
  if (usage.isError) return <ErrorState message={usage.error.message} onRetry={() => void usage.refetch()} />;

  return (
    <div className="space-y-3">
      <WalletCard data={data} />

      <HourlyChart hours={summary.hours} />

      <div className="grid gap-3 sm:grid-cols-2">
        <Card className="p-4">
          <p className="text-sm font-black">{t("botReseller.byService")}</p>
          {summary.byService.length ? (
            summary.byService.map(([name, s]) => (
              <div key={name} className="mt-3">
                <div className="flex justify-between text-xs">
                  <span className="font-bold">{name}</span>
                  <span className="text-muted">
                    {formatBytes(s.bytes, 1)} · {formatToman(s.amount)}
                  </span>
                </div>
                <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-2">
                  <div className="h-full rounded-full bg-primary" style={{ width: `${clampPercent(s.bytes, summary.bytes || 1)}%` }} />
                </div>
              </div>
            ))
          ) : (
            <p className="mt-3 text-xs text-muted">{t("botReseller.noUsage")}</p>
          )}
        </Card>
        <Card className="p-4">
          <p className="text-sm font-black">{t("botReseller.topUsers")}</p>
          {top.length ? (
            top.map((user, i) => (
              <div key={user.id} className="mt-2.5 flex items-center justify-between gap-2 text-xs">
                <span className="flex min-w-0 items-center gap-2">
                  <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-surface-2 text-[10px] font-black text-muted">{formatNumber(i + 1)}</span>
                  <span className="truncate font-bold" dir="ltr">
                    {user.username || user.name}
                  </span>
                </span>
                <span className="shrink-0 tabular-nums text-muted">{formatBytes(user.used_bytes, 1)}</span>
              </div>
            ))
          ) : (
            <p className="mt-3 text-xs text-muted">{t("botReseller.noUsers")}</p>
          )}
        </Card>
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        {data.services.map((service) => (
          <ServiceCard key={service.id} service={service} />
        ))}
      </div>

      <h3 className="px-1 text-sm font-black">{t("botReseller.recentCharges")}</h3>
      <ChargesList rows={rows} loading={false} error={null} />
    </div>
  );
}

const nowSeconds = () => Math.floor(Date.now() / 1000);

function useNow(intervalMs = 30_000): number {
  const [now, setNow] = useState(nowSeconds);
  useEffect(() => {
    const id = window.setInterval(() => setNow(nowSeconds()), intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs]);
  return now;
}

type Translate = (key: string, options?: Record<string, unknown>) => string;

function formatRemaining(expire: number | null, now: number, t: Translate): string {
  if (!expire) return t("botReseller.remaining.unlimited");
  const diff = expire - now;
  if (diff <= 0) return t("botReseller.remaining.expired");
  const days = Math.floor(diff / 86400);
  const hours = Math.floor((diff % 86400) / 3600);
  const minutes = Math.floor((diff % 3600) / 60);
  const parts = [
    days ? t("botReseller.remaining.days", { n: formatNumber(days) }) : "",
    hours ? t("botReseller.remaining.hours", { n: formatNumber(hours) }) : "",
    minutes || (!days && !hours) ? t("botReseller.remaining.minutes", { n: formatNumber(Math.max(1, minutes)) }) : "",
  ].filter(Boolean);
  return t("botReseller.remaining.left", { time: parts.join(" ") });
}

function volumeText(user: BotResellerUserItem): string {
  if (!user.live) return "—";
  if (!user.limit_bytes) return `${formatBytes(user.used_bytes, 1)} / ∞`;
  return `${formatNumber(Math.round((user.used_bytes / GB) * 10) / 10)} / ${formatBytes(user.limit_bytes)}`;
}

function isOnline(user: BotResellerUserItem, now: number): boolean {
  return user.online_at != null && now - user.online_at <= ONLINE_WINDOW_S;
}

function isActive(user: BotResellerUserItem): boolean {
  return !user.disabled_by && user.status === "active";
}

function usedPercent(user: BotResellerUserItem): number {
  return user.limit_bytes ? clampPercent(user.used_bytes, user.limit_bytes) : 0;
}

function daysLeft(user: BotResellerUserItem, now: number): number | null {
  return user.expire ? Math.max(0, Math.ceil((user.expire - now) / 86400)) : null;
}

function runningOut(user: BotResellerUserItem, now: number): boolean {
  if (!isActive(user)) return false;
  const days = daysLeft(user, now);
  return (days != null && days <= SOON_DAYS) || usedPercent(user) >= SOON_PERCENT;
}

type UserFilter = "all" | "online" | "active" | "disabled" | "soon";
type UserSort = "recent" | "usage" | "online" | "expire" | "name";

function matchesFilter(user: BotResellerUserItem, filter: UserFilter, now: number): boolean {
  if (filter === "online") return isOnline(user, now);
  if (filter === "active") return isActive(user);
  if (filter === "disabled") return !isActive(user);
  if (filter === "soon") return runningOut(user, now);
  return true;
}

const SORTERS: Record<UserSort, (a: BotResellerUserItem, b: BotResellerUserItem) => number> = {
  recent: (a, b) => b.id - a.id,
  usage: (a, b) => b.used_bytes - a.used_bytes,
  online: (a, b) => (b.online_at || 0) - (a.online_at || 0),
  expire: (a, b) => (a.expire || Number.MAX_SAFE_INTEGER) - (b.expire || Number.MAX_SAFE_INTEGER),
  name: (a, b) => (a.username || a.name).localeCompare(b.username || b.name),
};

const STAT_ITEMS: { key: UserFilter; icon: LucideIcon; tone: string; ring: string }[] = [
  { key: "all", icon: Users, tone: "text-text", ring: "bg-primary/10" },
  { key: "online", icon: Wifi, tone: "text-success", ring: "bg-success/10" },
  { key: "active", icon: CircleCheck, tone: "text-primary", ring: "bg-primary/10" },
  { key: "disabled", icon: Ban, tone: "text-danger", ring: "bg-danger/10" },
  { key: "soon", icon: Hourglass, tone: "text-warning", ring: "bg-warning/10" },
];

function UserStats({ users, value, onChange, now }: { users: BotResellerUserItem[]; value: UserFilter; onChange: (v: UserFilter) => void; now: number }) {
  const { t } = useTranslation();
  return (
    <Card className="grid grid-cols-5 divide-x divide-border overflow-hidden p-0 rtl:divide-x-reverse">
      {STAT_ITEMS.map((item) => {
        const count = users.filter((u) => matchesFilter(u, item.key, now)).length;
        const active = value === item.key;
        const Icon = item.icon;
        return (
          <button
            key={item.key}
            type="button"
            onClick={() => onChange(active ? "all" : item.key)}
            className={`flex min-w-0 flex-col items-center gap-1 px-1 py-2.5 transition-colors ${active ? item.ring : "hover:bg-surface-2/50"}`}
          >
            <span className={`flex items-center gap-1 ${item.tone}`}>
              <Icon size={14} />
              {item.key === "online" && count > 0 && <LiveDot />}
            </span>
            <b className={`text-base font-black leading-none tabular-nums ${item.tone}`}>{formatNumber(count)}</b>
            <span className="w-full truncate text-center text-[10px] text-muted">{t(`botReseller.stats.${item.key}`)}</span>
          </button>
        );
      })}
    </Card>
  );
}

function UserAvatar({ user, now, size = 32 }: { user: BotResellerUserItem; now: number; size?: number }) {
  const label = (user.name || user.username).slice(0, 2).toUpperCase();
  return (
    <span className="relative shrink-0" style={{ width: size, height: size }}>
      <span className={`grid h-full w-full place-items-center rounded-full text-xs font-black ${isActive(user) ? "bg-primary/15 text-primary" : "bg-surface-2 text-muted"}`}>{label}</span>
      {isOnline(user, now) && (
        <span className="absolute -bottom-0.5 -start-0.5 flex h-3 w-3">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-60" />
          <span className="relative inline-flex h-3 w-3 rounded-full border-2 border-surface bg-success" />
        </span>
      )}
    </span>
  );
}

function userTone(user: BotResellerUserItem): "success" | "warning" | "danger" | "muted" {
  if (user.disabled_by) return "muted";
  if (user.status === "active") return "success";
  if (user.status === "limited" || user.status === "expired") return "warning";
  return "danger";
}

function UserStatus({ user }: { user: BotResellerUserItem }) {
  const { t } = useTranslation();
  const label = user.disabled_by ? t(`botReseller.disabledBy.${user.disabled_by}`) : t(`botReseller.status.${user.status || "unknown"}`, user.status || "-");
  return <Badge tone={userTone(user)}>{label}</Badge>;
}

function UsageBar({ user }: { user: BotResellerUserItem }) {
  const p = usedPercent(user);
  const tone = p >= 90 ? "bg-danger" : p >= SOON_PERCENT - 15 ? "bg-warning" : "bg-success";
  return (
    <div className="h-1 w-full overflow-hidden rounded-full bg-surface-2">
      <div className={`h-full rounded-full ${user.limit_bytes ? tone : "bg-border"}`} style={{ width: `${user.limit_bytes ? p : 100}%` }} />
    </div>
  );
}

function lastSeen(user: BotResellerUserItem, now: number, t: (k: string) => string): string {
  if (isOnline(user, now)) return t("botReseller.onlineNow");
  return user.online_at ? formatRelativeTime(user.online_at) : t("botReseller.neverOnline");
}

function IconMenu<T extends string>({ icon: Icon, label, value, defaultValue, options, onChange }: { icon: LucideIcon; label: string; value: T; defaultValue: T; options: { value: T; label: string }[]; onChange: (v: T) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);
  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-label={label}
        title={label}
        onClick={() => setOpen((v) => !v)}
        className={`relative grid h-8 w-8 place-items-center rounded-lg transition-colors ${open || value !== defaultValue ? "bg-primary/15 text-primary" : "text-muted hover:bg-surface hover:text-text"}`}
      >
        <Icon size={16} />
        {value !== defaultValue && <span className="absolute end-1 top-1 h-1.5 w-1.5 rounded-full bg-primary" />}
      </button>
      <AnimatePresence>
        {open && (
          <m.div
            initial={{ opacity: 0, y: -4, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.98 }}
            transition={{ duration: 0.12 }}
            className="absolute end-0 top-10 z-40 min-w-44 overflow-hidden rounded-xl bg-surface p-1 shadow-2xl shadow-black/40 ring-1 ring-border"
          >
            <p className="px-2.5 pb-1 pt-1.5 text-[11px] font-bold text-muted">{label}</p>
            {options.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => {
                  onChange(option.value);
                  setOpen(false);
                }}
                className={`flex w-full items-center justify-between gap-3 rounded-lg px-2.5 py-2 text-start text-sm transition-colors hover:bg-surface-2 ${option.value === value ? "font-bold text-primary" : "text-text"}`}
              >
                {option.label}
                {option.value === value && <Check size={14} />}
              </button>
            ))}
          </m.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function UsersTab({ onOpen, onCreate, blocked }: { onOpen: (id: number) => void; onCreate: () => void; blocked: boolean }) {
  const { t } = useTranslation();
  const users = useBotResellerUsers(true);
  const [service, setService] = useState("all");
  const [filter, setFilter] = useState<UserFilter>("all");
  const [sort, setSort] = useState<UserSort>("recent");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const now = useNow();

  const all = users.data?.users || [];
  const services = useMemo(() => {
    const seen = new Map<number, string>();
    for (const u of all) seen.set(u.service_id, u.service_name);
    return [...seen.entries()];
  }, [all]);

  const rows = useMemo(() => {
    const now = nowSeconds();
    const needle = q.trim().toLowerCase();
    return all
      .filter(
        (u) =>
          (service === "all" || String(u.service_id) === service) &&
          matchesFilter(u, filter, now) &&
          (!needle || u.username.toLowerCase().includes(needle) || u.name.includes(needle) || (u.note || "").toLowerCase().includes(needle))
      )
      .sort(SORTERS[sort]);
  }, [all, service, filter, sort, q]);

  useEffect(() => setPage(1), [service, filter, sort, q]);

  if (users.isLoading) return <SkeletonCard />;
  if (users.isError) return <ErrorState message={users.error.message} onRetry={() => void users.refetch()} />;
  if (!all.length) return <EmptyState icon={Bot} title={t("botReseller.noUsers")} description={t("botReseller.noUsersHint")} />;

  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const current = Math.min(page, totalPages);
  const shown = rows.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE);
  const filtered = filter !== "all" || service !== "all" || q.trim() !== "";

  return (
    <div className="space-y-3">
      {users.data?.live_error && <p className="text-xs text-warning">{t("botReseller.liveError")}</p>}
      <UserStats users={all} value={filter} onChange={setFilter} now={now} />

      <div className="relative z-30 flex items-center gap-2">
        <div className="flex h-11 min-w-0 flex-1 items-center gap-1 rounded-xl bg-surface-2/60 ps-3 pe-1.5 ring-1 ring-inset ring-border focus-within:ring-2 focus-within:ring-primary/50">
          <Search size={16} className="shrink-0 text-muted" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("botReseller.search")} className="h-full min-w-0 flex-1 bg-transparent px-1 text-sm outline-none placeholder:text-muted" />
          {q && (
            <button type="button" onClick={() => setQ("")} aria-label={t("botReseller.clearSearch")} className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-muted hover:bg-surface hover:text-text">
              <X size={15} />
            </button>
          )}
          <span className="mx-0.5 h-5 w-px shrink-0 bg-border" />
          {services.length > 1 && (
            <IconMenu
              icon={Layers}
              label={t("botReseller.service")}
              value={service}
              defaultValue="all"
              onChange={setService}
              options={[{ value: "all", label: t("botReseller.allServices") }, ...services.map(([id, name]) => ({ value: String(id), label: name }))]}
            />
          )}
          <IconMenu<UserSort>
            icon={ArrowUpDown}
            label={t("botReseller.sortBy")}
            value={sort}
            defaultValue="recent"
            onChange={setSort}
            options={(["recent", "usage", "online", "expire", "name"] as UserSort[]).map((value) => ({ value, label: t(`botReseller.sort.${value}`) }))}
          />
        </div>
        <Button className="h-11 shrink-0" onClick={onCreate} disabled={blocked} aria-label={t("botReseller.newUser")}>
          <Plus size={16} />
          <span className="hidden sm:inline">{t("botReseller.newUser")}</span>
        </Button>
      </div>

      <div className="flex items-center justify-between px-1 text-xs text-muted">
        <span>{t("botReseller.resultCount", { count: rows.length, shown: formatNumber(rows.length) })}</span>
        {filtered && (
          <button
            type="button"
            className="font-bold text-primary"
            onClick={() => {
              setFilter("all");
              setService("all");
              setQ("");
            }}
          >
            {t("botReseller.clearFilters")}
          </button>
        )}
      </div>

      {shown.length ? (
        <Card className="overflow-hidden p-0">
          <div className="hidden grid-cols-[minmax(0,2.2fr)_minmax(0,1fr)_minmax(0,1.6fr)_minmax(0,1fr)_auto] gap-3 bg-surface-2/60 px-4 py-2.5 text-[11px] font-bold text-muted sm:grid">
            <span>{t("botReseller.col.user")}</span>
            <span>{t("botReseller.col.service")}</span>
            <span>{t("botReseller.col.usage")}</span>
            <span>{t("botReseller.col.expire")}</span>
            <span className="w-16 text-end">{t("botReseller.col.status")}</span>
          </div>
          <div className="divide-y divide-border">
            {shown.map((user) => {
              const days = daysLeft(user, now);
              const remaining = formatRemaining(user.expire, now, t);
              const soon = days != null && days <= SOON_DAYS;
              return (
                <button
                  key={user.id}
                  type="button"
                  onClick={() => onOpen(user.id)}
                  className="grid w-full grid-cols-1 items-center gap-3 px-4 py-3 text-start transition-colors hover:bg-surface-2/50 sm:grid-cols-[minmax(0,2.2fr)_minmax(0,1fr)_minmax(0,1.6fr)_minmax(0,1fr)_auto]"
                >
                  <span className="flex min-w-0 items-center gap-2.5">
                    <UserAvatar user={user} now={now} />
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center justify-between gap-2">
                        <span className="truncate text-sm font-bold" dir="ltr">
                          {user.username || user.name}
                        </span>
                        <span className="shrink-0 sm:hidden">
                          <UserStatus user={user} />
                        </span>
                      </span>
                      <span className={`block truncate text-[11px] ${isOnline(user, now) ? "text-success" : "text-muted"}`}>
                        {lastSeen(user, now, t)}
                        <span className="text-muted sm:hidden">
                          {" · "}
                          {user.service_name}
                        </span>
                        {user.note ? <span className="text-muted"> · {user.note}</span> : null}
                      </span>
                      <span className="mt-1.5 flex items-center justify-between gap-2 whitespace-nowrap text-[11px] tabular-nums sm:hidden">
                        <span className="truncate font-bold text-text">{volumeText(user)}</span>
                        <span className={`truncate ${soon ? "font-bold text-warning" : "text-muted"}`}>{remaining}</span>
                      </span>
                      <span className="mt-1 block sm:hidden">
                        <UsageBar user={user} />
                      </span>
                    </span>
                  </span>
                  <span className="hidden truncate text-xs text-muted sm:block">{user.service_name}</span>
                  <span className="hidden min-w-0 sm:block">
                    <span className="block text-[11px] tabular-nums">{volumeText(user)}</span>
                    <span className="mt-1 block">
                      <UsageBar user={user} />
                    </span>
                  </span>
                  <span className={`hidden text-xs sm:block ${soon ? "font-bold text-warning" : "text-muted"}`}>{remaining}</span>
                  <span className="hidden justify-end sm:flex sm:w-16">
                    <UserStatus user={user} />
                  </span>
                </button>
              );
            })}
          </div>
        </Card>
      ) : (
        <Card className="p-8 text-center text-sm text-muted">{t("botReseller.noMatch")}</Card>
      )}

      {totalPages > 1 && (
        <div className="flex justify-center">
          <Pagination page={current} totalPages={totalPages} onChange={setPage} />
        </div>
      )}
    </div>
  );
}

const NAME_WORDS = ["sky", "nova", "pixel", "orbit", "echo", "zen", "flux", "luna", "storm", "fox", "wave", "jet", "neo", "atlas", "iris", "onyx"];

function randomName(): string {
  const word = NAME_WORDS[Math.floor(Math.random() * NAME_WORDS.length)];
  return `${word}${Math.floor(100 + Math.random() * 9900)}`;
}

const GB_PRESETS = [5, 10, 20, 30, 50, 100];
const DAY_PRESETS = [7, 15, 30, 60, 90];

function presetsFor(presets: number[], max: number): number[] {
  const within = presets.filter((p) => !max || p <= max);
  if (max && !within.includes(max)) within.push(max);
  return max ? within : [...within, 0];
}

function AmountPicker({
  icon: Icon,
  label,
  unit,
  value,
  onChange,
  presets,
  max,
  step,
}: {
  icon: LucideIcon;
  label: string;
  unit: string;
  value: number;
  onChange: (v: number) => void;
  presets: number[];
  max: number;
  step: number;
}) {
  const { t } = useTranslation();
  const clamp = (v: number) => Math.max(max ? step : 0, max ? Math.min(max, v) : v);
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-sm font-bold">
          <Icon size={15} className="text-muted" />
          {label}
        </span>
        <span className="text-[11px] text-muted">{max ? t("botReseller.upTo", { max: formatNumber(max), unit }) : t("botReseller.unlimitedAllowed")}</span>
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          aria-label="-"
          onClick={() => onChange(clamp(value - step))}
          className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-surface-2/60 text-text ring-1 ring-inset ring-border active:scale-95"
        >
          <Minus size={16} />
        </button>
        <label className="flex h-11 min-w-0 flex-1 items-center justify-center gap-1.5 rounded-xl bg-surface-2/60 px-3 ring-1 ring-inset ring-border focus-within:ring-2 focus-within:ring-primary/50">
          {value === 0 ? (
            <span className="flex items-center gap-1 text-sm font-black text-primary">
              <InfinityIcon size={18} />
              {t("botReseller.unlimited")}
            </span>
          ) : (
            <>
              <input
                inputMode="decimal"
                dir="ltr"
                value={String(value)}
                onChange={(e) => {
                  const n = Number(e.target.value.replace(/[^\d.]/g, ""));
                  if (Number.isFinite(n)) onChange(max ? Math.min(max, n) : n);
                }}
                className="w-16 bg-transparent text-center text-base font-black tabular-nums outline-none"
              />
              <span className="text-xs text-muted">{unit}</span>
            </>
          )}
        </label>
        <button
          type="button"
          aria-label="+"
          onClick={() => onChange(clamp((value || 0) + step))}
          className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-surface-2/60 text-text ring-1 ring-inset ring-border active:scale-95"
        >
          <Plus size={16} />
        </button>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {presets.map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => onChange(p)}
            className={`flex h-8 items-center gap-1 rounded-full px-3 text-xs font-bold tabular-nums transition-colors ${value === p ? "bg-primary text-primary-text" : "bg-surface-2/60 text-muted ring-1 ring-inset ring-border hover:text-text"}`}
          >
            {p === 0 ? <InfinityIcon size={14} /> : `${formatNumber(p)} ${unit}`}
          </button>
        ))}
      </div>
    </div>
  );
}

function CreateUserSheet({ open, onClose, services, prefix, suffix }: { open: boolean; onClose: () => void; services: BotResellerServiceItem[]; prefix: string; suffix: string }) {
  const { t } = useTranslation();
  const toast = useToast();
  const { haptic } = useTelegram();
  const [serviceId, setServiceId] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [gb, setGb] = useState(10);
  const [days, setDays] = useState(30);
  const [note, setNote] = useState("");
  const [link, setLink] = useState<string | null>(null);
  const create = useBotResellerMutation(botResellerApi.createUser);

  const service = services.find((s) => s.id === serviceId) || services[0];
  const maxGb = service?.max_user_gb || 0;
  const maxDays = service?.max_user_days || 0;
  const nameOk = NAME_RE.test(name);
  const fullName = [prefix, name || "…", suffix].filter(Boolean).join("_");

  useEffect(() => {
    if (maxGb && (gb === 0 || gb > maxGb)) setGb(Math.min(10, maxGb));
    if (maxDays && (days === 0 || days > maxDays)) setDays(Math.min(30, maxDays));
  }, [maxGb, maxDays]);

  const close = () => {
    setName("");
    setNote("");
    setLink(null);
    onClose();
  };

  const submit = () => {
    if (!service) return;
    create.mutate(
      { service_id: service.id, name, gb, days, note: note || null },
      {
        onSuccess: (res) => {
          haptic.notify("success");
          setLink(res.subscription_url || "");
          toast.show(t("botReseller.created"), "success");
        },
        onError: (err) => toast.show(err.message, "error"),
      }
    );
  };

  return (
    <Sheet
      open={open}
      onClose={close}
      title={link != null ? t("botReseller.createdTitle") : t("botReseller.newUser")}
      footer={
        link != null ? (
          <Button fullWidth onClick={close}>
            {t("botReseller.done")}
          </Button>
        ) : (
          <div className="space-y-2">
            <p className="flex items-center justify-center gap-1.5 text-[11px] text-muted">
              <Wallet size={12} />
              {gb > 0 && service ? t("botReseller.maxCost", { cost: formatToman(gb * service.price_per_gb) }) : t("botReseller.payPerUse")}
            </p>
            <Button fullWidth loading={create.isPending} disabled={!service || !nameOk} onClick={submit}>
              <UserPlus size={16} />
              {t("botReseller.createAndLink")}
            </Button>
          </div>
        )
      }
    >
      {link != null ? (
        <div className="space-y-3">
          {link && <SubscriptionQr url={link} />}
          <CopyField label={t("botReseller.subLink")} value={link} wrap />
        </div>
      ) : (
        <div className="space-y-5">
          <div className="space-y-2">
            <span className="flex items-center gap-1.5 text-sm font-bold">
              <Layers size={15} className="text-muted" />
              {t("botReseller.service")}
            </span>
            <div className="space-y-2">
              {services.map((s) => {
                const active = service?.id === s.id;
                return (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => setServiceId(s.id)}
                    className={`flex w-full items-center gap-3 rounded-2xl p-3 text-start ring-1 ring-inset transition-colors ${active ? "bg-primary/10 ring-primary/50" : "bg-surface-2/50 ring-border hover:bg-surface-2"}`}
                  >
                    <span className={`grid h-5 w-5 shrink-0 place-items-center rounded-full ring-2 ring-inset ${active ? "bg-primary text-primary-text ring-primary" : "ring-border"}`}>
                      {active && <Check size={12} strokeWidth={3} />}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-bold">{s.name}</span>
                      <span className="mt-0.5 flex flex-wrap gap-x-2 text-[11px] text-muted">
                        <span>{s.max_user_gb ? t("botReseller.upTo", { max: formatNumber(s.max_user_gb), unit: "GB" }) : t("botReseller.unlimitedVolume")}</span>
                        <span>·</span>
                        <span>{s.max_user_days ? t("botReseller.upTo", { max: formatNumber(s.max_user_days), unit: t("botReseller.dayUnit") }) : t("botReseller.unlimitedTime")}</span>
                      </span>
                    </span>
                    <span className="shrink-0 rounded-full bg-surface px-2.5 py-1 text-[11px] font-black tabular-nums text-primary ring-1 ring-inset ring-border">
                      {t("botReseller.perGb", { price: formatNumber(s.price_per_gb) })}
                    </span>
                  </button>
                );
              })}
            </div>
            <p className="text-[11px] text-muted">{t("botReseller.serviceLocked")}</p>
          </div>

          <div className="space-y-2">
            <span className="flex items-center gap-1.5 text-sm font-bold">
              <AtSign size={15} className="text-muted" />
              {t("botReseller.name")}
            </span>
            <div className={`flex h-11 items-center gap-1 rounded-xl bg-surface-2/60 ps-3 pe-1.5 ring-1 ring-inset focus-within:ring-2 ${name && !nameOk ? "ring-danger/60 focus-within:ring-danger/60" : "ring-border focus-within:ring-primary/50"}`}>
              <input
                dir="ltr"
                value={name}
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
                placeholder="ali_2025"
                onChange={(e) => setName(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""))}
                className="h-full min-w-0 flex-1 bg-transparent text-sm font-bold outline-none placeholder:font-normal placeholder:text-muted"
              />
              <button
                type="button"
                onClick={() => {
                  setName(randomName());
                  haptic.impact("light");
                }}
                aria-label={t("botReseller.randomName")}
                title={t("botReseller.randomName")}
                className="flex h-8 shrink-0 items-center gap-1 rounded-lg bg-primary/15 px-2.5 text-xs font-bold text-primary active:scale-95"
              >
                <Dices size={15} />
                {t("botReseller.random")}
              </button>
            </div>
            <p className={`text-[11px] ${name && !nameOk ? "text-danger" : "text-muted"}`}>
              {name && !nameOk ? (
                t("botReseller.nameRule")
              ) : (
                <>
                  {t("botReseller.finalName")}:{" "}
                  <b className="font-mono text-primary" dir="ltr">
                    {fullName}
                  </b>
                </>
              )}
            </p>
          </div>

          <AmountPicker icon={HardDrive} label={t("botReseller.volume")} unit="GB" value={gb} onChange={setGb} presets={presetsFor(GB_PRESETS, maxGb)} max={maxGb} step={5} />
          <AmountPicker icon={CalendarDays} label={t("botReseller.days")} unit={t("botReseller.dayUnit")} value={days} onChange={setDays} presets={presetsFor(DAY_PRESETS, maxDays)} max={maxDays} step={1} />

          <div className="space-y-2">
            <span className="flex items-center gap-1.5 text-sm font-bold">
              <StickyNote size={15} className="text-muted" />
              {t("botReseller.note")}
            </span>
            <input
              value={note}
              maxLength={200}
              onChange={(e) => setNote(e.target.value)}
              placeholder={t("botReseller.notePlaceholder")}
              className="h-11 w-full rounded-xl bg-surface-2/60 px-3 text-sm outline-none ring-1 ring-inset ring-border placeholder:text-muted focus:ring-2 focus:ring-primary/50"
            />
          </div>
        </div>
      )}
    </Sheet>
  );
}

function SubscriptionQr({ url }: { url: string }) {
  const { t } = useTranslation();
  const [src, setSrc] = useState("");
  useEffect(() => {
    let cancelled = false;
    QRCode.toDataURL(url, { width: 280, margin: 1, color: { dark: "#10131c", light: "#ffffff" } })
      .then((data: string) => !cancelled && setSrc(data))
      .catch(() => !cancelled && setSrc(""));
    return () => {
      cancelled = true;
    };
  }, [url]);
  return (
    <div className="flex flex-col items-center gap-2 rounded-2xl bg-surface-2/50 p-4 ring-1 ring-inset ring-border">
      <div className="rounded-xl bg-white p-2">
        {src ? <img src={src} alt={t("botReseller.qrTitle")} className="h-44 w-44" /> : <div className="h-44 w-44 animate-pulse rounded-lg bg-surface-2" />}
      </div>
      <p className="text-xs text-muted">{t("botReseller.qrHint")}</p>
    </div>
  );
}

function ActionTile({ icon: Icon, label, onClick, loading, disabled, active, tone = "default" }: { icon: LucideIcon; label: string; onClick: () => void; loading?: boolean; disabled?: boolean; active?: boolean; tone?: "default" | "warning" | "success" | "danger" }) {
  const color = { default: "text-text", warning: "text-warning", success: "text-success", danger: "text-danger" }[tone];
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || loading}
      className={`flex min-w-0 flex-col items-center gap-1.5 rounded-2xl px-1 py-3 ring-1 ring-inset transition-colors disabled:opacity-40 ${active ? "bg-primary/15 text-primary ring-primary/50" : `bg-surface-2/60 ring-border hover:bg-surface-2 ${color}`}`}
    >
      {loading ? <RefreshCw size={19} className="animate-spin" /> : <Icon size={19} />}
      <span className="w-full truncate text-center text-[11px] font-bold">{label}</span>
    </button>
  );
}

const RENEW_DAYS = [7, 15, 30, 60, 90];
const RENEW_GB = [5, 10, 20, 50, 100];

function RenewPanel({ user, service, now, onDone }: { user: BotResellerUserItem; service?: BotResellerServiceItem; now: number; onDone: () => void }) {
  const { t } = useTranslation();
  const toast = useToast();
  const edit = useBotResellerMutation(botResellerApi.editUser);
  const reset = useBotResellerMutation(botResellerApi.resetUsage);

  const maxDays = service?.max_user_days || 0;
  const maxGb = service?.max_user_gb || 0;
  const currentDays = user.expire ? Math.max(0, Math.ceil((user.expire - now) / 86400)) : 0;
  const currentGb = Math.round((user.limit_bytes / GB) * 100) / 100;
  const daysRoom = maxDays ? Math.max(0, maxDays - currentDays) : Infinity;
  const gbRoom = maxGb ? Math.max(0, Math.round((maxGb - currentGb) * 100) / 100) : Infinity;
  const usedMost = user.limit_bytes > 0 && user.used_bytes >= user.limit_bytes * 0.5;

  const [addDays, setAddDays] = useState(() => (user.expire ? Math.min(30, daysRoom) : 0));
  const [addGb, setAddGb] = useState(0);
  const [resetUsage, setResetUsage] = useState(() => user.limit_bytes > 0 && gbRoom === 0 && usedMost);

  const newDays = user.expire ? currentDays + addDays : 0;
  const newGb = user.limit_bytes ? Math.round((currentGb + addGb) * 100) / 100 : 0;
  const nothing = addDays === 0 && addGb === 0 && !resetUsage;

  const save = async () => {
    try {
      if (resetUsage) await reset.mutateAsync({ id: user.id });
      if (addDays || addGb) await edit.mutateAsync({ id: user.id, gb: newGb, days: newDays, note: user.note });
      toast.show(t("botReseller.renewed"), "success");
      onDone();
    } catch (err) {
      toast.show((err as Error).message, "error");
    }
  };

  const chips = (values: number[], room: number, value: number, onChange: (v: number) => void, unit: string) => {
    const options = values.filter((v) => v <= room);
    if (Number.isFinite(room) && room > 0 && !options.includes(room)) options.push(room);
    return (
      <div className="flex flex-wrap gap-1.5">
        {options.map((v) => {
          const toCap = Number.isFinite(room) && v === room;
          return (
            <button
              key={v}
              type="button"
              onClick={() => onChange(value === v ? 0 : v)}
              className={`flex h-8 items-center gap-1 rounded-full px-3 text-xs font-bold tabular-nums transition-colors ${value === v ? "bg-primary text-primary-text" : "bg-surface-2/60 text-muted ring-1 ring-inset ring-border hover:text-text"}`}
            >
              +{formatNumber(v)} {unit}
              {toCap && <span className="text-[10px] font-normal opacity-80">({t("botReseller.toCap")})</span>}
            </button>
          );
        })}
      </div>
    );
  };

  const capNotice = (text: string) => (
    <p className="flex items-start gap-2 rounded-xl bg-warning/10 px-3 py-2 text-xs leading-relaxed text-warning ring-1 ring-inset ring-warning/30">
      <AlertTriangle size={14} className="mt-0.5 shrink-0" />
      {text}
    </p>
  );

  return (
    <div className="space-y-4 rounded-2xl bg-surface-2/40 p-3 ring-1 ring-inset ring-border">
      {user.expire ? (
        <div className="space-y-2">
          <span className="flex items-center justify-between gap-2 text-xs font-bold">
            <span className="flex items-center gap-1.5">
              <CalendarPlus size={14} className="text-muted" />
              {t("botReseller.addTime")}
            </span>
            {maxDays > 0 && <span className="font-normal text-muted">{t("botReseller.capOf", { max: formatNumber(maxDays), unit: t("botReseller.dayUnit") })}</span>}
          </span>
          {daysRoom === 0 ? capNotice(t("botReseller.daysAtCap", { max: formatNumber(maxDays) })) : chips(RENEW_DAYS, daysRoom, addDays, setAddDays, t("botReseller.dayUnit"))}
        </div>
      ) : null}

      {user.limit_bytes ? (
        <div className="space-y-2">
          <span className="flex items-center justify-between gap-2 text-xs font-bold">
            <span className="flex items-center gap-1.5">
              <HardDrive size={14} className="text-muted" />
              {t("botReseller.addVolume")}
            </span>
            {maxGb > 0 && <span className="font-normal text-muted">{t("botReseller.capOf", { max: formatNumber(maxGb), unit: "GB" })}</span>}
          </span>
          {gbRoom === 0 ? capNotice(t("botReseller.volumeAtCap", { max: formatNumber(maxGb) })) : chips(RENEW_GB, gbRoom, addGb, setAddGb, "GB")}
        </div>
      ) : null}

      <button type="button" onClick={() => setResetUsage((v) => !v)} className="flex w-full items-center justify-between gap-2 text-xs">
        <span className="flex items-center gap-1.5 font-bold">
          <RotateCcw size={14} className="text-muted" />
          {t("botReseller.resetOnRenew")}
          {gbRoom === 0 && user.limit_bytes > 0 && <span className="rounded-full bg-primary/15 px-1.5 py-0.5 text-[10px] text-primary">{t("botReseller.suggested")}</span>}
        </span>
        <span className={`relative h-5 w-9 rounded-full transition-colors ${resetUsage ? "bg-primary" : "bg-border"}`}>
          <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all ${resetUsage ? "end-0.5" : "start-0.5"}`} />
        </span>
      </button>

      <div className="grid grid-cols-2 gap-2 rounded-xl bg-surface p-2.5 text-xs">
        <div>
          <p className="text-muted">{t("botReseller.timeLeft")}</p>
          <p className="mt-0.5 font-semibold tabular-nums">
            {user.expire ? (
              <>
                {formatNumber(currentDays)} → <span className={addDays ? "text-success" : ""}>{formatNumber(newDays)}</span> {t("botReseller.dayUnit")}
              </>
            ) : (
              t("botReseller.unlimited")
            )}
          </p>
        </div>
        <div>
          <p className="text-muted">{resetUsage ? t("botReseller.freeAfter") : t("botReseller.totalVolume")}</p>
          <p className="mt-0.5 font-semibold tabular-nums">
            {!user.limit_bytes ? (
              t("botReseller.unlimited")
            ) : resetUsage ? (
              <>
                {formatBytes(Math.max(0, user.limit_bytes - user.used_bytes), 1)} → <span className="text-success">{formatNumber(newGb)} GB</span>
              </>
            ) : (
              <>
                {formatNumber(currentGb)} → <span className={addGb ? "text-success" : ""}>{formatNumber(newGb)}</span> GB
              </>
            )}
          </p>
        </div>
      </div>

      <Button fullWidth disabled={nothing} loading={edit.isPending || reset.isPending} onClick={() => void save()}>
        <CalendarPlus size={16} />
        {t("botReseller.applyRenew")}
      </Button>
    </div>
  );
}

function EditPanel({ user, service, now, onDone }: { user: BotResellerUserItem; service?: BotResellerServiceItem; now: number; onDone: () => void }) {
  const { t } = useTranslation();
  const toast = useToast();
  const edit = useBotResellerMutation(botResellerApi.editUser);
  const maxGb = service?.max_user_gb || 0;
  const maxDays = service?.max_user_days || 0;
  const [gb, setGb] = useState(user.limit_bytes ? Math.round((user.limit_bytes / GB) * 100) / 100 : 0);
  const [days, setDays] = useState(user.expire ? Math.max(0, Math.ceil((user.expire - now) / 86400)) : 0);
  const [note, setNote] = useState(user.note || "");

  return (
    <div className="space-y-4 rounded-2xl bg-surface-2/40 p-3 ring-1 ring-inset ring-border">
      <AmountPicker icon={HardDrive} label={t("botReseller.volume")} unit="GB" value={gb} onChange={setGb} presets={presetsFor(GB_PRESETS, maxGb)} max={maxGb} step={5} />
      <AmountPicker icon={CalendarDays} label={t("botReseller.daysFromNow")} unit={t("botReseller.dayUnit")} value={days} onChange={setDays} presets={presetsFor(DAY_PRESETS, maxDays)} max={maxDays} step={1} />
      <div className="space-y-2">
        <span className="flex items-center gap-1.5 text-sm font-bold">
          <StickyNote size={15} className="text-muted" />
          {t("botReseller.note")}
        </span>
        <input
          value={note}
          maxLength={200}
          onChange={(e) => setNote(e.target.value)}
          placeholder={t("botReseller.notePlaceholder")}
          className="h-11 w-full rounded-xl bg-surface px-3 text-sm outline-none ring-1 ring-inset ring-border placeholder:text-muted focus:ring-2 focus:ring-primary/50"
        />
      </div>
      <Button
        fullWidth
        loading={edit.isPending}
        onClick={() =>
          edit.mutate(
            { id: user.id, gb, days, note: note || null },
            {
              onSuccess: () => {
                toast.show(t("botReseller.saved"), "success");
                onDone();
              },
              onError: (err) => toast.show(err.message, "error"),
            }
          )
        }
      >
        <Check size={16} />
        {t("botReseller.save")}
      </Button>
    </div>
  );
}

type Panel = "renew" | "edit" | "qr" | null;
type Risky = "disable" | "reset" | "revoke" | "delete";

const RISKY_ICON: Record<Risky, LucideIcon> = { disable: PowerOff, reset: RotateCcw, revoke: Link2, delete: Trash2 };

function ConfirmBox({ action, name, loading, onConfirm, onCancel }: { action: Risky; name: string; loading: boolean; onConfirm: () => void; onCancel: () => void }) {
  const { t } = useTranslation();
  const Icon = RISKY_ICON[action];
  const danger = action === "delete";
  return (
    <div className={`space-y-3 rounded-2xl p-3 ring-1 ring-inset ${danger ? "bg-danger/10 ring-danger/40" : "bg-warning/10 ring-warning/40"}`}>
      <div className="flex items-start gap-2.5">
        <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl ${danger ? "bg-danger/15 text-danger" : "bg-warning/15 text-warning"}`}>
          <Icon size={17} />
        </span>
        <div className="min-w-0">
          <p className="text-sm font-black">{t(`botReseller.confirm.${action}.title`)}</p>
          <p className="mt-0.5 text-xs text-muted">{t(`botReseller.confirm.${action}.body`, { name })}</p>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Button variant="secondary" onClick={onCancel} disabled={loading}>
          {t("botReseller.cancel")}
        </Button>
        <Button variant={danger ? "danger" : "primary"} loading={loading} onClick={onConfirm}>
          {t(`botReseller.confirm.${action}.yes`)}
        </Button>
      </div>
    </div>
  );
}

function UserSheet({ id, onClose, services, blocked }: { id: number | null; onClose: () => void; services: BotResellerServiceItem[]; blocked: boolean }) {
  const { t } = useTranslation();
  const toast = useToast();
  const detail = useBotResellerUser(id);
  const now = useNow();
  const [panel, setPanel] = useState<Panel>(null);
  const [confirming, setConfirming] = useState<Risky | null>(null);
  const toggle = useBotResellerMutation(botResellerApi.toggleUser);
  const revoke = useBotResellerMutation(botResellerApi.revokeLink);
  const reset = useBotResellerMutation(botResellerApi.resetUsage);
  const remove = useBotResellerMutation(botResellerApi.deleteUser);

  const user = detail.data?.user;
  const service = services.find((s) => s.id === user?.service_id);

  const close = () => {
    setPanel(null);
    setConfirming(null);
    onClose();
  };
  const done = (message: string) => ({
    onSuccess: () => toast.show(message, "success"),
    onError: (err: Error) => toast.show(err.message, "error"),
  });
  const flip = (next: Panel) => {
    setConfirming(null);
    setPanel((current) => (current === next ? null : next));
  };
  const ask = (action: Risky) => {
    setPanel(null);
    setConfirming((current) => (current === action ? null : action));
  };

  const runConfirmed = () => {
    if (!user || !confirming) return;
    const finish = (message: string, after?: () => void) => ({
      onSuccess: () => {
        toast.show(message, "success");
        setConfirming(null);
        after?.();
      },
      onError: (err: Error) => toast.show(err.message, "error"),
    });
    if (confirming === "disable") toggle.mutate({ id: user.id, enabled: false }, finish(t("botReseller.disabled")));
    else if (confirming === "reset") reset.mutate({ id: user.id }, finish(t("botReseller.resetDone")));
    else if (confirming === "revoke") revoke.mutate({ id: user.id }, finish(t("botReseller.linkChanged")));
    else remove.mutate({ id: user.id }, finish(t("botReseller.deleted"), close));
  };
  const confirmLoading = toggle.isPending || reset.isPending || revoke.isPending || remove.isPending;

  const percent = user ? usedPercent(user) : 0;
  const remainingDays = user ? daysLeft(user, now) : null;
  const soon = remainingDays != null && remainingDays <= SOON_DAYS;

  return (
    <Sheet open={id != null} onClose={close} title={user?.username || user?.name || t("botReseller.user")} subtitle={user?.service_name}>
      {detail.isLoading || !user ? (
        detail.isError ? <ErrorState message={detail.error.message} /> : <SkeletonCard />
      ) : (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <UserAvatar user={user} now={now} size={48} />
            <div className="min-w-0 flex-1">
              <p className="truncate text-base font-black" dir="ltr">
                {user.username || user.name}
              </p>
              <p className={`flex items-center gap-1 text-xs ${isOnline(user, now) ? "text-success" : "text-muted"}`}>
                <Wifi size={12} />
                {isOnline(user, now) ? t("botReseller.onlineNow") : `${t("botReseller.lastOnline")}: ${lastSeen(user, now, t)}`}
              </p>
            </div>
            <UserStatus user={user} />
          </div>

          <div className="space-y-3 rounded-2xl bg-surface-2/50 p-4 ring-1 ring-inset ring-border">
            <div className="flex items-center gap-4">
              <ProgressRing
                percent={user.limit_bytes ? Math.round(percent) : 100}
                size={84}
                strokeWidth={8}
                tone={percent >= 90 ? "danger" : percent >= SOON_PERCENT - 15 ? "warning" : "primary"}
              />
              <div className="min-w-0 flex-1 space-y-1">
                <p className="text-[11px] text-muted">{t("botReseller.used")}</p>
                <p className="text-lg font-semibold leading-tight tabular-nums">
                  {formatBytes(user.used_bytes, 1)}
                  <span className="text-sm font-normal text-muted"> / {user.limit_bytes ? formatBytes(user.limit_bytes) : t("botReseller.unlimited")}</span>
                </p>
                {user.limit_bytes > 0 && (
                  <p className="text-xs text-muted">
                    {t("botReseller.volumeLeft")}: <span className="text-text tabular-nums">{formatBytes(Math.max(0, user.limit_bytes - user.used_bytes), 1)}</span>
                  </p>
                )}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <StatTile icon={Clock} label={t("botReseller.timeLeft")} value={formatRemaining(user.expire, now, t)} tone={soon ? "warning" : undefined} wide />
              <StatTile icon={Wallet} label={t("botReseller.costSoFar")} value={formatToman(user.cost)} />
              <StatTile icon={CalendarDays} label={t("botReseller.expire")} value={user.expire ? formatUnixDate(user.expire) : t("botReseller.unlimited")} />
            </div>
          </div>

          {user.note && (
            <p className="flex items-center gap-2 rounded-xl bg-surface-2/50 px-3 py-2 text-xs text-muted">
              <StickyNote size={13} className="shrink-0" />
              {user.note}
            </p>
          )}

          <div className="grid grid-cols-4 gap-2">
            <ActionTile icon={CalendarPlus} label={t("botReseller.renew")} active={panel === "renew"} disabled={blocked} onClick={() => flip("renew")} />
            <ActionTile icon={SlidersHorizontal} label={t("botReseller.editShort")} active={panel === "edit"} disabled={blocked} onClick={() => flip("edit")} />
            <ActionTile icon={QrCode} label={t("botReseller.qrShort")} active={panel === "qr"} disabled={!detail.data?.subscription_url} onClick={() => flip("qr")} />
            {user.disabled_by === "reseller" ? (
              <ActionTile icon={Power} tone="success" label={t("botReseller.enable")} disabled={blocked} loading={toggle.isPending} onClick={() => toggle.mutate({ id: user.id, enabled: true }, done(t("botReseller.enabled")))} />
            ) : (
              <ActionTile icon={PowerOff} tone="warning" label={t("botReseller.disable")} active={confirming === "disable"} disabled={!!user.disabled_by} onClick={() => ask("disable")} />
            )}
            <ActionTile icon={Link2} label={t("botReseller.newLink")} active={confirming === "revoke"} disabled={blocked} onClick={() => ask("revoke")} />
            <ActionTile icon={RotateCcw} label={t("botReseller.resetUsage")} active={confirming === "reset"} disabled={blocked} onClick={() => ask("reset")} />
            <ActionTile icon={Trash2} tone="danger" label={t("botReseller.deleteShort")} active={confirming === "delete"} onClick={() => ask("delete")} />
          </div>

          {confirming && (
            <ConfirmBox action={confirming} name={user.username || user.name} loading={confirmLoading} onConfirm={runConfirmed} onCancel={() => setConfirming(null)} />
          )}

          <AnimatePresence initial={false} mode="wait">
            {panel && (
              <m.div key={panel} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.15 }}>
                {panel === "renew" && <RenewPanel user={user} service={service} now={now} onDone={() => setPanel(null)} />}
                {panel === "edit" && <EditPanel user={user} service={service} now={now} onDone={() => setPanel(null)} />}
                {panel === "qr" && detail.data?.subscription_url && <SubscriptionQr url={detail.data.subscription_url} />}
              </m.div>
            )}
          </AnimatePresence>

          {detail.data?.subscription_url && <CopyField label={t("botReseller.subLink")} value={detail.data.subscription_url} wrap />}
        </div>
      )}
    </Sheet>
  );
}

function StatTile({ icon: Icon, label, value, tone, wide }: { icon: LucideIcon; label: string; value: string; tone?: "warning"; wide?: boolean }) {
  return (
    <div className={`rounded-xl bg-surface/70 px-3 py-2.5 ring-1 ring-inset ring-border/60 ${wide ? "col-span-2" : ""}`}>
      <p className="flex items-center gap-1.5 text-[11px] text-muted">
        <Icon size={12} />
        {label}
      </p>
      <p className={`mt-1 text-sm font-medium leading-snug tabular-nums ${tone === "warning" ? "text-warning" : "text-text"}`}>{value}</p>
    </div>
  );
}
