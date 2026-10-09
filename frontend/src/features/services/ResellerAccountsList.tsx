import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { CalendarClock, Flame, Plus, Store, Users, Wallet } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Badge, Card, EmptyState, IconBadge } from "../../components/ui";
import { useTelegram } from "../../hooks/useTelegram";
import { formatNumber, formatToman } from "../../lib/format";
import { STATUS_TONE, formatRunway, resellerModeLabel, runwayTone, statusLabels } from "../../lib/resellerLabels";
import { daysUntil, isExpiringSoon } from "../../lib/serviceHelpers";
import type { ResellerAccountItem, WebAppResellerAccountsResponse } from "../../types/webapp";

const listVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.05, delayChildren: 0.03 } },
} as const;

const itemVariants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { type: "spring" as const, stiffness: 420, damping: 30 } },
};

function AccountCard({ account }: { account: ResellerAccountItem }) {
  const { t } = useTranslation();
  const { haptic } = useTelegram();
  const expired = account.status === "expired";
  const expiringSoon = !expired && isExpiringSoon(account.expiration_timestamp);
  const days = daysUntil(account.expiration_timestamp);
  const tone = expiringSoon ? "warning" : STATUS_TONE[account.status] || "muted";

  return (
    <motion.div variants={itemVariants} layout>
      <Link to={`/services/reseller/${account.code}`} onClick={() => haptic.select()} className="block h-full">
        <motion.article
          whileTap={{ scale: 0.985 }}
          className={`flex h-full flex-col gap-3 rounded-lg border bg-surface p-3.5 shadow-sm transition-colors hover:border-primary/30 ${
            expiringSoon ? "border-warning/40" : "border-border"
          } ${expired ? "opacity-60" : ""}`}
        >
          <div className="flex items-center gap-3">
            <IconBadge icon={Store} tone={tone} size="md" />
            <div className="min-w-0 flex-1">
              <h2 className="truncate text-sm font-bold text-text" dir="ltr" style={{ textAlign: "start" }}>
                {account.username}
              </h2>
              <p className="mt-0.5 truncate text-[11px] text-muted">
                {[account.panel_name, resellerModeLabel(t, account.pricing_mode)].filter(Boolean).join(" · ")}
              </p>
            </div>
            <Badge tone={tone}>
              {expiringSoon ? t("services.expiringSoon") : statusLabels(t)[account.status] || account.status}
            </Badge>
          </div>
          <div className="flex items-center justify-between gap-2 border-t border-border pt-2.5 text-xs text-muted">
            <span className="flex items-center gap-1.5">
              <Users size={13} />
              <b className="font-semibold text-text">
                {account.max_users ? formatNumber(account.max_users) : t("reseller.unlimitedUsers")}
              </b>
            </span>
            {days != null ? (
              <span className={`flex items-center gap-1.5 ${expiringSoon ? "text-warning" : ""}`}>
                <CalendarClock size={13} />
                <span>
                  <b className={`font-semibold ${expiringSoon ? "text-warning" : "text-text"}`}>{formatNumber(days)}</b>{" "}
                  {t("services.daysLeft")}
                </span>
              </span>
            ) : (
              <span>{t("reseller.noExpiry")}</span>
            )}
          </div>
        </motion.article>
      </Link>
    </motion.div>
  );
}

export default function ResellerAccountsList({
  data,
  chips,
}: {
  data: WebAppResellerAccountsResponse;
  chips: ReactNode;
}) {
  const { t } = useTranslation();
  const { haptic } = useTelegram();
  const burning = data.burn_per_hour > 0;

  return (
    <div className="space-y-4">
      <motion.header
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
        className="flex items-center gap-3"
      >
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-bold tracking-tight text-text">{t("reseller.list.title")}</h1>
          <p className="text-sm text-muted">
            {t("reseller.list.subtitle", { count: formatNumber(data.accounts.length) })}
          </p>
        </div>
        {data.can_buy && (
          <Link
            to="/buy"
            onClick={() => haptic.select()}
            aria-label={t("services.buyNew")}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-primary text-primary-text shadow-sm transition-colors hover:bg-primary/90"
          >
            <Plus size={20} />
          </Link>
        )}
      </motion.header>

      {chips}

      {burning && (
        <Card className="flex items-center gap-3 p-3.5">
          <IconBadge icon={Wallet} tone="accent" size="md" />
          <div className="min-w-0 flex-1">
            <p className="text-xs text-muted">{t("reseller.list.wallet")}</p>
            <p className="truncate text-base font-extrabold text-text">{formatToman(data.balance)}</p>
            <p className="mt-0.5 flex items-center gap-1 text-[11px] text-muted">
              <Flame size={11} />
              {t("reseller.perHour", { amount: formatToman(data.burn_per_hour) })}
            </p>
          </div>
          <div className="shrink-0 text-end">
            <p className="text-[11px] text-muted">{t("reseller.runway")}</p>
            <Badge tone={runwayTone(data.runway_hours, 24)}>{formatRunway(t, data.runway_hours)}</Badge>
          </div>
        </Card>
      )}

      {data.accounts.length === 0 ? (
        <EmptyState icon={Store} title={t("reseller.list.empty")} />
      ) : (
        <motion.div
          variants={listVariants}
          initial="hidden"
          animate="show"
          className="grid gap-3 md:grid-cols-2 xl:grid-cols-3"
        >
          {data.accounts.map((account) => (
            <AccountCard key={account.code} account={account} />
          ))}
        </motion.div>
      )}
    </div>
  );
}
