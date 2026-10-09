import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { CalendarClock, ChevronRight, Database, Plus, Search, Satellite, Server } from "lucide-react";
import { useTranslation } from "react-i18next";
import { EmojiIcon } from "../../components/EmojiIcon";
import { ChipTabs, EmptyState, IconBadge, Input, Pagination, SegmentedControl, SkeletonCard } from "../../components/ui";
import { ErrorState } from "../../components/ui/EmptyState";
import { Badge } from "../../components/ui/Badge";
import { useTelegram } from "../../hooks/useTelegram";
import { daysUntil, isExpiringSoon, statusLabel, statusTone } from "../../lib/serviceHelpers";
import { formatBytes, formatNumber } from "../../lib/format";
import { useResellerAccounts } from "../../queries/useReseller";
import ResellerAccountsList from "./ResellerAccountsList";
import { useServicesQuery } from "../../queries/useServices";
import type { PanelGroupItem, ServiceStatus } from "../../types/webapp";

const LIMIT_OPTIONS = [5, 10, 20] as const;
const LIMIT_SEGMENTS = LIMIT_OPTIONS.map((n) => ({ value: String(n), label: String(n) }));

const listVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.06, delayChildren: 0.04 },
  },
} as const;

const itemVariants = {
  hidden: { opacity: 0, y: 16, scale: 0.98 },
  show: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { type: "spring" as const, stiffness: 420, damping: 28 },
  },
};

function ServiceCard({ service }: { service: ServiceStatus }) {
  const { t } = useTranslation();
  const { haptic } = useTelegram();
  const expired = (service.status || "").toLowerCase() === "expired";
  const expiringSoon = !expired && isExpiringSoon(service.expiration_timestamp);
  const days = daysUntil(service.expiration_timestamp);
  const tone = statusTone(service.status);
  const badgeTone = expiringSoon ? "warning" : tone.badge;
  const badgeLabel = expiringSoon ? t("services.expiringSoon") : statusLabel(service.status);
  const subtitle = [service.panel_name, `${t("services.code")} ${formatNumber(Number(service.code))}`]
    .filter(Boolean)
    .join(" · ");

  return (
    <motion.div variants={itemVariants} layout>
      <Link to={`/services/${service.code}`} onClick={() => haptic.select()} className="block h-full">
        <motion.article
          whileTap={{ scale: 0.985 }}
          className={`flex h-full flex-col gap-3 rounded-lg border bg-surface p-3.5 shadow-sm transition-colors hover:border-primary/30 ${
            expiringSoon ? "border-warning/40" : "border-border"
          } ${expired ? "opacity-60" : ""}`}
        >
          <div className="flex items-center gap-3">
            <IconBadge icon={Server} tone={expired ? "danger" : expiringSoon ? "warning" : "primary"} size="md" />
            <div className="min-w-0 flex-1">
              <h2 className="truncate text-sm font-bold text-text" dir="ltr" style={{ textAlign: "start" }}>
                {service.username}
              </h2>
              <p className="mt-0.5 truncate text-[11px] text-muted">{subtitle}</p>
            </div>
            <Badge tone={badgeTone}>{badgeLabel}</Badge>
          </div>

          {!expired && (
            <div className="flex items-center justify-between gap-2 border-t border-border pt-2.5 text-xs text-muted">
              <span className="flex items-center gap-1.5">
                <Database size={13} />
                <b className="font-semibold text-text">
                  {service.total_traffic_bytes > 0 ? formatBytes(service.total_traffic_bytes) : t("services.unlimited")}
                </b>
              </span>
              {days != null && (
                <span className={`flex items-center gap-1.5 ${expiringSoon ? "text-warning" : ""}`}>
                  <CalendarClock size={13} />
                  <span>
                    <b className={`font-semibold ${expiringSoon ? "text-warning" : "text-text"}`}>{formatNumber(days)}</b>{" "}
                    {t("services.daysLeft")}
                  </span>
                </span>
              )}
            </div>
          )}
        </motion.article>
      </Link>
    </motion.div>
  );
}

function PanelGroupCard({ group, onSelect, t }: { group: PanelGroupItem; onSelect: () => void; t: (key: string) => string }) {
  const { haptic } = useTelegram();
  return (
    <motion.div variants={itemVariants} layout>
      <motion.button
        type="button"
        onClick={() => {
          haptic.select();
          onSelect();
        }}
        whileHover={{ y: -2 }}
        whileTap={{ scale: 0.985 }}
        className="group w-full overflow-hidden rounded-lg border border-border bg-surface p-4 text-right shadow-sm transition hover:border-primary/50"
      >
        <div className="flex items-center gap-4">
          <div className="rounded-md bg-primary/10 p-3 text-primary ring-1 ring-primary/20">
            <EmojiIcon id="globe_with_meridians" size={26} />
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate font-bold text-text">{group.panel_name}</p>
            <p className="mt-1 text-xs text-muted">
              {group.service_count.toLocaleString()} {t("services.servicePanel")}
            </p>
          </div>
          <span className="rounded-full bg-surface-2 px-3 py-1 text-xs text-primary ring-1 ring-border transition group-hover:bg-primary/15">
            {t("services.view")}
          </span>
        </div>
      </motion.button>
    </motion.div>
  );
}

function VpnServicesList({ chips }: { chips: ReactNode }) {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState<number>(5);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [selectedPanel, setSelectedPanel] = useState<PanelGroupItem | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(searchQuery), 300);
    return () => window.clearTimeout(timer);
  }, [searchQuery]);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, limit, selectedPanel]);

  const { data, isLoading, error, refetch } = useServicesQuery(
    page,
    limit,
    debouncedSearch,
    selectedPanel?.panel_code ?? null
  );

  const groupingEnabled = data?.grouping_enabled ?? false;
  const showPanelGroups = groupingEnabled && selectedPanel === null;
  const panelGroups = data?.panel_groups ?? [];
  const services = data?.services ?? [];
  const total = data?.total ?? 0;
  const totalPages = data?.total_pages ?? 0;

  return (
    <div className="space-y-5">
      <motion.header
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
        className="relative space-y-1 pe-12"
      >
        <BuyNewButton />
        {selectedPanel ? (
          <button
            type="button"
            onClick={() => setSelectedPanel(null)}
            className="mb-1 flex items-center gap-1.5 text-sm font-medium text-primary"
          >
            <ChevronRight size={16} />
            {t("services.backToPanel")}
          </button>
        ) : null}
        <h1 className="text-2xl font-bold tracking-tight text-text">
          {selectedPanel ? selectedPanel.panel_name : t("services.title")}
        </h1>
        <p className="text-sm text-muted">
          {showPanelGroups
            ? t("services.panelServicesDesc")
            : total > 0
              ? `${total} ${t("services.activeServices")}`
              : t("services.manageServices")}
        </p>
      </motion.header>

      {chips}

      {!showPanelGroups && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05, duration: 0.3 }}
          className="relative"
        >
          <Search size={16} className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-muted" />
          <Input
            type="search"
            placeholder={t("services.searchPlaceholder")}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pr-10"
          />
        </motion.div>
      )}

      {error && <ErrorState message={(error as Error).message} onRetry={() => void refetch()} />}

      {isLoading ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : showPanelGroups ? (
        panelGroups.length === 0 ? (
          <EmptyState
            icon={Server}
            title={t("services.noPanels")}
            description={t("services.noPanelsDesc")}
          />
        ) : (
          <motion.div variants={listVariants} initial="hidden" animate="show" className="grid gap-3 md:grid-cols-2">
            {panelGroups.map((group) => (
              <PanelGroupCard
                key={group.panel_code}
                group={group}
                onSelect={() => setSelectedPanel(group)}
                t={t}
              />
            ))}
          </motion.div>
        )
      ) : services.length === 0 ? (
        <EmptyState
          icon={Satellite}
          title={t("services.noServices")}
          description={t("services.noServicesDesc")}
        />
      ) : (
        <>
          <AnimatePresence mode="wait">
            <motion.div
              key={`${page}-${limit}-${debouncedSearch}-${selectedPanel?.panel_code ?? "all"}`}
              variants={listVariants}
              initial="hidden"
              animate="show"
              className="grid gap-3 md:grid-cols-2 xl:grid-cols-3"
            >
              {services.map((svc) => (
                <ServiceCard key={svc.code} service={svc} />
              ))}
            </motion.div>
          </AnimatePresence>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.15 }}
            className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4"
          >
            <div className="flex items-center gap-2.5 text-sm text-muted">
              <span className="whitespace-nowrap">{t("services.perPage")}</span>
              <SegmentedControl
                options={LIMIT_SEGMENTS}
                value={String(limit)}
                onChange={(v) => setLimit(Number(v))}
                columns={LIMIT_SEGMENTS.length}
              />
            </div>
            <Pagination page={page} totalPages={totalPages || 1} onChange={setPage} />
          </motion.div>
        </>
      )}
    </div>
  );
}

function BuyNewButton() {
  const { t } = useTranslation();
  const { haptic } = useTelegram();
  return (
    <Link
      to="/buy"
      onClick={() => haptic.select()}
      aria-label={t("services.buyNew")}
      title={t("services.buyNew")}
      className="absolute end-0 top-0 flex h-10 w-10 items-center justify-center rounded-md bg-primary text-primary-text shadow-sm transition-colors hover:bg-primary/90"
    >
      <Plus size={20} />
    </Link>
  );
}

type ServicesTab = "vpn" | "reseller";

/** VPN services, plus a "Reseller" chip once the user owns a reseller account. */
export default function ServicesListPage() {
  const { t } = useTranslation();
  const { haptic } = useTelegram();
  const [searchParams, setSearchParams] = useSearchParams();
  const resellers = useResellerAccounts();
  const resellerCount = resellers.data?.accounts.length ?? 0;
  const tab: ServicesTab = searchParams.get("tab") === "reseller" && resellerCount > 0 ? "reseller" : "vpn";

  const chips =
    resellerCount > 0 ? (
      <ChipTabs<ServicesTab>
        options={[
          { value: "vpn", label: t("services.vpnTab") },
          { value: "reseller", label: t("services.resellerTab"), count: resellerCount },
        ]}
        value={tab}
        onChange={(value) => {
          haptic.select();
          setSearchParams(value === "reseller" ? { tab: "reseller" } : {}, { replace: true });
        }}
      />
    ) : null;

  return tab === "reseller" && resellers.data ? (
    <ResellerAccountsList data={resellers.data} chips={chips} />
  ) : (
    <VpnServicesList chips={chips} />
  );
}
