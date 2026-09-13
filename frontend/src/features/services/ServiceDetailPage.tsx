import { useEffect, useState, type ReactNode } from "react";
import QRCode from "qrcode";
import { useNavigate, useParams } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  ArrowDownToLine,
  ArrowRightLeft,
  BarChart3,
  CalendarDays,
  Check,
  Clock,
  Coins,
  Copy,
  Database,
  HardDrive,
  Layers,
  Link2,
  Pencil,
  PlusCircle,
  QrCode,
  RefreshCw,
  Repeat,
  TimerReset,
  Users,
  Globe2,
  Wifi,
  type LucideIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { PageHeader } from "../../components/layout/PageHeader";
import { Badge, Button, Card, Modal, Skeleton, SkeletonCard } from "../../components/ui";
import { ErrorState } from "../../components/ui/EmptyState";
import { useTelegram } from "../../hooks/useTelegram";
import { useWebAppAuth } from "../../hooks/useWebAppAuth";
import { copyToClipboard, formatBytes, formatExpiry, formatRelativeTime, formatToman } from "../../lib/format";
import { statusLabel, statusTone } from "../../lib/serviceHelpers";
import {
  useChangeLinkMutation,
  useChangeSubscriptionMutation,
  useServiceDetailQuery,
} from "../../queries/useServices";
import type { ServiceButtons } from "../../types/webapp";
import { ClientsSheet } from "./ClientsSheet";
import { ConfigLinksSheet } from "./ConfigLinksSheet";
import { TransferConfigSheet } from "./TransferConfigSheet";
import { UsageChartSheet } from "./UsageChartPanel";

const fadeUp = {
  hidden: { opacity: 0, y: 14 },
  show: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: 0.04 * i, duration: 0.35, ease: [0.22, 1, 0.36, 1] as const },
  }),
};

const tileGridVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.05 } },
};

const tileVariants = {
  hidden: { opacity: 0, y: 10, scale: 0.97 },
  show: { opacity: 1, y: 0, scale: 1, transition: { type: "spring" as const, stiffness: 460, damping: 30 } },
};

function StatCell({ icon: Icon, label, value }: { icon?: LucideIcon; label: string; value: string }) {
  return (
    <div className="rounded-md bg-surface-2/70 px-3 py-2.5 shadow-sm ring-1 ring-border">
      <p className="flex items-center gap-1 text-[11px] text-muted">
        {Icon && <Icon size={11} />}
        {label}
      </p>
      <p className="mt-1 truncate text-sm font-semibold text-text">{value}</p>
    </div>
  );
}

function InfoRow({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 px-3.5 py-2.5">
      <span className="flex items-center gap-1.5 text-xs text-muted">
        <Icon size={13} />
        {label}
      </span>
      <span className="truncate text-xs font-semibold text-text" dir="ltr">
        {value}
      </span>
    </div>
  );
}

function ActionTile({
  icon: Icon,
  label,
  hint,
  onClick,
  loading = false,
  danger = false,
}: {
  icon: LucideIcon;
  label: string;
  hint?: string;
  onClick: () => void;
  loading?: boolean;
  danger?: boolean;
}) {
  return (
    <motion.button
      type="button"
      variants={tileVariants}
      whileHover={{ y: -2 }}
      whileTap={{ scale: 0.96 }}
      transition={{ type: "spring", stiffness: 500, damping: 28 }}
      disabled={loading}
      onClick={onClick}
      className={`flex items-center gap-2.5 rounded-lg border px-3 py-2.5 text-right transition-colors disabled:opacity-50 ${
        danger
          ? "border-danger/20 bg-danger/5 hover:border-danger/40 hover:bg-danger/10"
          : "border-border bg-surface hover:border-primary/35 hover:bg-primary/5"
      }`}
    >
      <span
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md ${
          danger ? "bg-danger/10 text-danger" : "bg-primary/10 text-primary"
        }`}
      >
        <Icon size={16} strokeWidth={1.9} className={loading ? "animate-spin" : ""} />
      </span>
      <span className="min-w-0 flex-1">
        <span className={`block truncate text-[13px] font-semibold ${danger ? "text-danger" : "text-text"}`}>
          {label}
        </span>
        {hint && <span className="block truncate text-[10.5px] leading-4 text-muted">{hint}</span>}
      </span>
    </motion.button>
  );
}

function CopyButton({
  label,
  value,
  copiedKey,
  activeKey,
  onCopied,
}: {
  label: string;
  value: string;
  copiedKey: string;
  activeKey: string | null;
  onCopied: (key: string) => void;
}) {
  const { t } = useTranslation();
  const copied = activeKey === copiedKey;
  return (
    <motion.button
      type="button"
      whileTap={{ scale: 0.98 }}
      onClick={() => {
        void copyToClipboard(value).then(() => onCopied(copiedKey));
      }}
      className={`flex w-full items-center justify-between gap-3 rounded-lg border px-4 py-3.5 text-sm font-medium transition-colors ${
        copied
          ? "border-success/30 bg-success/10 text-success"
          : "border-border bg-surface text-text hover:border-primary/40 hover:bg-primary/5"
      }`}
    >
      <span className="flex items-center gap-2">
        <AnimatePresence mode="wait" initial={false}>
          {copied ? (
            <motion.span key="ok" initial={{ scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}>
              <Check size={18} />
            </motion.span>
          ) : (
            <motion.span key="copy" initial={{ scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}>
              <Copy size={18} />
            </motion.span>
          )}
        </AnimatePresence>
        {copied ? t("serviceDetail.copied") : label}
      </span>
      <span className="max-w-[42%] truncate text-xs text-muted ltr-field" dir="ltr">
        {value}
      </span>
    </motion.button>
  );
}

function QrModal({
  open,
  onClose,
  subscriptionUrl,
  username,
}: {
  open: boolean;
  onClose: () => void;
  subscriptionUrl: string;
  username: string;
}) {
  const { t } = useTranslation();
  const [qrDataUrl, setQrDataUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!open || !subscriptionUrl) {
      setQrDataUrl("");
      return;
    }
    let cancelled = false;
    setLoading(true);
    QRCode.toDataURL(subscriptionUrl, {
      width: 280,
      margin: 1,
      color: { dark: "#10131c", light: "#ffffff" },
    })
      .then((url: string) => {
        if (!cancelled) {
          setQrDataUrl(url);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setQrDataUrl("");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [open, subscriptionUrl]);

  return (
    <Modal open={open} onClose={onClose} title={t("serviceDetail.qrTitle")}>
      <p className="mb-4 text-xs text-muted">{username}</p>
      <div className="flex flex-col items-center py-2">
        <motion.div
          initial={{ opacity: 0, scale: 0.92 }}
          animate={{ opacity: 1, scale: 1 }}
          className="rounded-lg border border-border bg-surface-2 p-4"
        >
          <div className="overflow-hidden rounded-md bg-white p-3">
            {loading ? (
              <Skeleton className="h-[280px] w-[280px]" />
            ) : qrDataUrl ? (
              <img src={qrDataUrl} alt="QR Code" className="h-[280px] w-[280px]" />
            ) : (
              <div className="flex h-[280px] w-[280px] items-center justify-center text-sm text-muted">
                {t("serviceDetail.qrError")}
              </div>
            )}
          </div>
        </motion.div>
        <p className="mt-4 text-center text-xs text-muted">{t("serviceDetail.qrSubtitle")}</p>
        <Button
          type="button"
          variant="secondary"
          className="mt-4"
          onClick={() => {
            void copyToClipboard(subscriptionUrl).then(() => {
              setCopied(true);
              window.setTimeout(() => setCopied(false), 1800);
            });
          }}
        >
          {copied ? <Check size={16} /> : <Copy size={16} />}
          {copied ? t("serviceDetail.linkCopied") : t("serviceDetail.copyLink")}
        </Button>
      </div>
    </Modal>
  );
}

function Section({ title, index, children }: { title: string; index: number; children: ReactNode }) {
  return (
    <motion.section custom={index} variants={fadeUp} initial="hidden" animate="show" className="space-y-3">
      <h3 className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">{title}</h3>
      {children}
    </motion.section>
  );
}

export default function ServiceDetailPage() {
  const { t } = useTranslation();
  const { code: codeParam } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const { ready } = useWebAppAuth();
  const { haptic } = useTelegram();

  const code = codeParam ? Number(codeParam) : null;

  const { data, isLoading, error, refetch } = useServiceDetailQuery(code);
  const changeLink = useChangeLinkMutation();
  const changeSub = useChangeSubscriptionMutation();

  const [copied, setCopied] = useState<string | null>(null);
  const [linksOpen, setLinksOpen] = useState(false);
  const [clientsOpen, setClientsOpen] = useState(false);
  const [usageOpen, setUsageOpen] = useState(false);
  const [transferOpen, setTransferOpen] = useState(false);
  const [qrOpen, setQrOpen] = useState(false);
  const [actionError, setActionError] = useState("");

  const service = data?.service ?? null;
  const buttons: ServiceButtons | null = data?.buttons ?? null;

  const copyWithFeedback = (key: string, value: string) => {
    void copyToClipboard(value).then(() => {
      haptic.notify("success");
      setCopied(key);
      window.setTimeout(() => setCopied((c) => (c === key ? null : c)), 1800);
    });
  };

  const handleChangeLink = () => {
    if (code == null) return;
    haptic.impact("medium");
    setActionError("");
    changeLink.mutate(code, {
      onSuccess: () => {
        haptic.notify("success");
        void refetch();
      },
      onError: (err) => setActionError((err as Error).message),
    });
  };

  const handleChangeSub = () => {
    if (code == null) return;
    haptic.impact("medium");
    setActionError("");
    changeSub.mutate(code, {
      onSuccess: (res) => {
        haptic.notify("success");
        if (res.subscription_url) copyWithFeedback("sub", res.subscription_url);
        void refetch();
      },
      onError: (err) => setActionError((err as Error).message),
    });
  };

  if (!ready || code == null || Number.isNaN(code)) {
    return (
      <div>
        <PageHeader title={t("serviceDetail.manageService")} back="/services" />
        <SkeletonCard />
      </div>
    );
  }

  if (isLoading) {
    return (
      <div>
        <PageHeader title={t("serviceDetail.manageService")} back="/services" />
        <SkeletonCard />
      </div>
    );
  }

  if (error || !service || !buttons) {
    return (
      <div>
        <PageHeader title={t("serviceDetail.manageService")} back="/services" />
        <ErrorState message={(error as Error)?.message || t("serviceDetail.serviceNotFound")} onRetry={() => void refetch()} />
      </div>
    );
  }

  const expiry = formatExpiry(service.expiration_timestamp);
  const tone = statusTone(service.status);
  const knownResetStrategies = ["day", "week", "month", "year"];
  const resetPeriodLabel =
    service.reset_strategy && knownResetStrategies.includes(service.reset_strategy)
      ? t(`resetStrategy.${service.reset_strategy}`)
      : null;
  const totalVolumeDisplay = resetPeriodLabel
    ? `${formatBytes(service.total_traffic_bytes)} (${resetPeriodLabel})`
    : formatBytes(service.total_traffic_bytes);

  const infoRows: Array<{ key: string; icon: LucideIcon; label: string; value: string }> = [
    { key: "used", icon: ArrowDownToLine, label: t("serviceDetail.used"), value: formatBytes(service.used_traffic_bytes, 2) },
    {
      key: "remaining",
      icon: HardDrive,
      label: t("serviceDetail.remaining"),
      value: formatBytes(service.remaining_traffic_bytes, 2),
    },
    {
      key: "lifetime",
      icon: Activity,
      label: t("serviceDetail.lifetimeUsage"),
      value: service.lifetime_used_traffic != null ? formatBytes(service.lifetime_used_traffic, 2) : "—",
    },
    ...(resetPeriodLabel
      ? [
          {
            key: "reset",
            icon: Repeat,
            label: t("serviceDetail.resetMode"),
            value: t("serviceDetail.resetsEvery", { period: resetPeriodLabel }),
          },
        ]
      : []),
    ...(service.total_possible_traffic != null
      ? [
          {
            key: "possible",
            icon: Layers,
            label: t("serviceDetail.possibleUsage"),
            value: formatBytes(service.total_possible_traffic, 1),
          },
        ]
      : []),
    { key: "expiry", icon: CalendarDays, label: t("serviceDetail.expiryDate"), value: expiry.date },
    {
      key: "value",
      icon: Coins,
      label: t("serviceDetail.approxValue"),
      value: service.config_value != null ? formatToman(service.config_value) : "—",
    },
    {
      key: "lastConn",
      icon: Wifi,
      label: t("serviceDetail.lastConnection"),
      value: service.last_connection ? formatRelativeTime(service.last_connection) : "—",
    },
    {
      key: "lastEdit",
      icon: Pencil,
      label: t("serviceDetail.lastEdit"),
      value: service.last_edit ? formatRelativeTime(service.last_edit) : "—",
    },
  ];

  const manageActions: Array<{
    key: string;
    icon: LucideIcon;
    label: string;
    hint: string;
    show: boolean;
    onClick: () => void;
  }> = [
    {
      key: "qr",
      icon: QrCode,
      label: t("serviceDetail.qr"),
      hint: t("serviceDetail.qrHint"),
      show: buttons.qr,
      onClick: () => {
        haptic.select();
        setQrOpen(true);
      },
    },
    {
      key: "links",
      icon: Globe2,
      label: t("serviceDetail.links"),
      hint: t("serviceDetail.linksHint"),
      show: buttons.other_links,
      onClick: () => {
        haptic.select();
        setLinksOpen(true);
      },
    },
    {
      key: "clients",
      icon: Users,
      label: t("serviceDetail.clients"),
      hint: t("serviceDetail.clientsHint"),
      show: buttons.client_list,
      onClick: () => {
        haptic.select();
        setClientsOpen(true);
      },
    },
    {
      key: "chart",
      icon: BarChart3,
      label: t("serviceDetail.usageChart"),
      hint: t("serviceDetail.usageChartHint"),
      show: !!buttons.usage_chart,
      onClick: () => {
        haptic.select();
        setUsageOpen(true);
      },
    },
    {
      key: "renew",
      icon: TimerReset,
      label: t("serviceDetail.renew"),
      hint: t("serviceDetail.renewHint"),
      show: buttons.tamdid,
      onClick: () => {
        haptic.select();
        navigate(`/services/${code}/renew`);
      },
    },
    {
      key: "extendTime",
      icon: Clock,
      label: t("serviceDetail.extendTime"),
      hint: t("serviceDetail.extendTimeHint"),
      show: !!buttons.extend_time,
      onClick: () => {
        haptic.select();
        navigate(`/services/${code}/extend-time`);
      },
    },
    {
      key: "extraVolume",
      icon: PlusCircle,
      label: t("serviceDetail.extraVolume"),
      hint: t("serviceDetail.extraVolumeHint"),
      show: !!buttons.extra_volume,
      onClick: () => {
        haptic.select();
        navigate(`/services/${code}/extra-volume`);
      },
    },
    {
      key: "transfer",
      icon: ArrowRightLeft,
      label: t("serviceDetail.transferConfig"),
      hint: t("serviceDetail.transferConfigHint"),
      show: !!buttons.transfer_config,
      onClick: () => {
        haptic.select();
        setTransferOpen(true);
      },
    },
  ];

  return (
    <div className="space-y-6 pb-2">
      <PageHeader
        title={service.username}
        subtitle={`${service.panel_name || t("serviceDetail.panel")} · ${t("serviceDetail.code")} ${service.code}`}
        back="/services"
      />

      {actionError && (
        <motion.p
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-md border border-danger/25 bg-danger/10 px-3 py-2 text-sm text-danger"
        >
          {actionError}
        </motion.p>
      )}

      <motion.div
        custom={0}
        variants={fadeUp}
        initial="hidden"
        animate="show"
        className="relative overflow-hidden rounded-lg border border-border bg-surface p-4 shadow-sm"
      >
        <div className="pointer-events-none absolute -left-10 -top-14 h-32 w-32 rounded-full bg-primary/10 blur-3xl" />

        <div className="relative flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5">
            <span className="relative flex h-2 w-2">
              <span
                className={`absolute inset-0 rounded-full opacity-40 blur-sm ${
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
            </span>
            <Badge tone={tone.badge}>{statusLabel(service.status)}</Badge>
          </div>
          <span className="text-xs text-muted">{t("serviceDetail.code")} {service.code}</span>
        </div>

        <div className="relative mt-4 grid grid-cols-2 gap-2.5">
          <StatCell icon={Clock} label={t("serviceDetail.remainingTime")} value={expiry.remaining} />
          <StatCell icon={Database} label={t("serviceDetail.totalVolume")} value={totalVolumeDisplay} />
        </div>
      </motion.div>

      <Section title={t("serviceDetail.serviceInfo")} index={1}>
        <Card className="divide-y divide-border overflow-hidden">
          {infoRows.map((row) => (
            <InfoRow key={row.key} icon={row.icon} label={row.label} value={row.value} />
          ))}
        </Card>
      </Section>

      {(buttons.copy_link || service.helper_subscription_url) && (
        <Section title={t("serviceDetail.subscriptionLink")} index={2}>
          <div className="space-y-2">
            {buttons.copy_link && service.subscription_url && (
              <CopyButton
                label={t("serviceDetail.copyMainLink")}
                value={service.subscription_url}
                copiedKey="main"
                activeKey={copied}
                onCopied={(key) => {
                  haptic.notify("success");
                  setCopied(key);
                  window.setTimeout(() => setCopied((c) => (c === key ? null : c)), 1800);
                }}
              />
            )}
            {service.helper_subscription_url && (
              <CopyButton
                label={t("serviceDetail.copyHelperLink")}
                value={service.helper_subscription_url}
                copiedKey="helper"
                activeKey={copied}
                onCopied={(key) => {
                  haptic.notify("success");
                  setCopied(key);
                  window.setTimeout(() => setCopied((c) => (c === key ? null : c)), 1800);
                }}
              />
            )}
          </div>
        </Section>
      )}

      <Section title={t("serviceDetail.actions")} index={3}>
        <motion.div
          variants={tileGridVariants}
          initial="hidden"
          animate="show"
          className="grid grid-cols-2 gap-2"
        >
          {manageActions
            .filter((a) => a.show)
            .map((action) => (
              <ActionTile
                key={action.key}
                icon={action.icon}
                label={action.label}
                hint={action.hint}
                onClick={action.onClick}
              />
            ))}
        </motion.div>
      </Section>

      {(buttons.change_link || buttons.change_sub) && !service.is_test && (
        <Section title={t("serviceDetail.accessSecurity")} index={4}>
          <motion.div
            variants={tileGridVariants}
            initial="hidden"
            animate="show"
            className="grid grid-cols-2 gap-2"
          >
            {buttons.change_link && (
              <ActionTile
                icon={RefreshCw}
                label={t("serviceDetail.changeLink")}
                hint={t("serviceDetail.changeLinkHint")}
                danger
                loading={changeLink.isPending}
                onClick={handleChangeLink}
              />
            )}
            {buttons.change_sub && (
              <ActionTile
                icon={Link2}
                label={t("serviceDetail.changeSub")}
                hint={t("serviceDetail.changeSubHint")}
                danger
                loading={changeSub.isPending}
                onClick={handleChangeSub}
              />
            )}
          </motion.div>
          <p className="text-[11px] leading-5 text-muted">{t("serviceDetail.changeSubWarning")}</p>
        </Section>
      )}

      <ConfigLinksSheet
        open={linksOpen}
        onClose={() => setLinksOpen(false)}
        code={code}
        username={service.username}
        fallbackLinks={service.single_config_links}
      />
      <ClientsSheet open={clientsOpen} onClose={() => setClientsOpen(false)} code={code} username={service.username} />
      <UsageChartSheet open={usageOpen} onClose={() => setUsageOpen(false)} code={code} username={service.username} />
      <TransferConfigSheet
        open={transferOpen}
        onClose={() => setTransferOpen(false)}
        code={code}
        username={service.username}
      />
      <QrModal
        open={qrOpen}
        onClose={() => setQrOpen(false)}
        subscriptionUrl={service.subscription_url ?? ""}
        username={service.username}
      />
    </div>
  );
}
