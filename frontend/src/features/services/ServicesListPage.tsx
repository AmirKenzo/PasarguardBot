import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronLeft, ChevronRight, Clock, Database, Search, Satellite, Server } from "lucide-react";
import { EmojiIcon } from "../../components/EmojiIcon";
import { EmptyState, Input, Pagination, SegmentedControl, SkeletonCard } from "../../components/ui";
import { ErrorState } from "../../components/ui/EmptyState";
import { Badge } from "../../components/ui/Badge";
import { useTelegram } from "../../hooks/useTelegram";
import { expiryParts, statusTone } from "../../lib/serviceHelpers";
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
  const { haptic } = useTelegram();
  const expiry = expiryParts(service.expiration_time);
  const tone = statusTone(service.status);

  return (
    <motion.div variants={itemVariants} layout>
      <Link
        to={`/services/${service.code}`}
        onClick={() => haptic.select()}
        className="block"
      >
        <motion.article
          whileHover={{ y: -1 }}
          whileTap={{ scale: 0.985 }}
          className="relative overflow-hidden rounded-lg border border-border bg-surface p-3.5 shadow-sm transition-colors hover:border-primary/30"
        >
          <div className="flex items-center gap-3">
            <div className="relative shrink-0">
              <span
                className={`absolute inset-0 rounded-full opacity-40 blur-md ${
                  tone.badge === "success"
                    ? "bg-success"
                    : tone.badge === "danger"
                      ? "bg-danger"
                      : tone.badge === "warning"
                        ? "bg-warning"
                        : "bg-muted"
                }`}
              />
              <span
                className={`relative block h-2 w-2 rounded-full ${
                  tone.badge === "success"
                    ? "bg-success"
                    : tone.badge === "danger"
                      ? "bg-danger"
                      : tone.badge === "warning"
                        ? "bg-warning"
                        : "bg-muted"
                }`}
              />
            </div>

            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <h2 className="truncate text-sm font-bold tracking-tight text-text">
                  {service.username}
                </h2>
                <Badge tone={tone.badge}>{service.status_text}</Badge>
              </div>
              <div className="mt-1 flex items-center gap-2.5 text-[11px] text-muted">
                <span className="flex items-center gap-1">
                  <Clock size={11} />
                  {expiry.remaining}
                </span>
                <span className="flex items-center gap-1">
                  <Database size={11} />
                  {service.total_traffic}
                </span>
              </div>
            </div>

            <ChevronLeft size={16} className="shrink-0 text-muted/70" />
          </div>
        </motion.article>
      </Link>
    </motion.div>
  );
}

function PanelGroupCard({ group, onSelect }: { group: PanelGroupItem; onSelect: () => void }) {
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
              {group.service_count.toLocaleString("fa-IR")} سرویس در این پنل
            </p>
          </div>
          <span className="rounded-full bg-surface-2 px-3 py-1 text-xs text-primary ring-1 ring-border transition group-hover:bg-primary/15">
            مشاهده
          </span>
        </div>
      </motion.button>
    </motion.div>
  );
}

export default function ServicesListPage() {
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
        className="space-y-1"
      >
        {selectedPanel ? (
          <button
            type="button"
            onClick={() => setSelectedPanel(null)}
            className="mb-1 flex items-center gap-1.5 text-sm font-medium text-primary"
          >
            <ChevronRight size={16} />
            بازگشت به پنل‌ها
          </button>
        ) : null}
        <h1 className="text-2xl font-bold tracking-tight text-text">
          {selectedPanel ? selectedPanel.panel_name : "سرویس‌ها"}
        </h1>
        <p className="text-sm text-muted">
          {showPanelGroups
            ? "پنل‌هایی که از آن‌ها سرویس خریداری کرده‌اید"
            : total > 0
              ? `${total} سرویس فعال در حساب شما`
              : "سرویس‌های حساب خود را اینجا مدیریت کنید"}
        </p>
      </motion.header>

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
            placeholder="جستجوی نام یا کد سرویس..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pr-10"
          />
        </motion.div>
      )}

      {error && <ErrorState message={(error as Error).message} onRetry={() => void refetch()} />}

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : showPanelGroups ? (
        panelGroups.length === 0 ? (
          <EmptyState
            icon={Server}
            title="سرویسی یافت نشد"
            description="هنوز از هیچ پنلی سرویسی خریداری نکرده‌اید."
          />
        ) : (
          <motion.div variants={listVariants} initial="hidden" animate="show" className="space-y-3">
            {panelGroups.map((group) => (
              <PanelGroupCard
                key={group.panel_code}
                group={group}
                onSelect={() => setSelectedPanel(group)}
              />
            ))}
          </motion.div>
        )
      ) : services.length === 0 ? (
        <EmptyState
          icon={Satellite}
          title="سرویسی یافت نشد"
          description="هنوز سرویسی ثبت نشده یا نتیجه‌ای برای جستجو پیدا نشد."
        />
      ) : (
        <>
          <AnimatePresence mode="wait">
            <motion.div
              key={`${page}-${limit}-${debouncedSearch}-${selectedPanel?.panel_code ?? "all"}`}
              variants={listVariants}
              initial="hidden"
              animate="show"
              className="space-y-3"
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
              <span className="whitespace-nowrap">در هر صفحه</span>
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
