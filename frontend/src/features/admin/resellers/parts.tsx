import { useTranslation } from "react-i18next";
import { Badge, EmptyState } from "../../../components/ui";
import { formatRelativeTime, formatToman, formatUnixDate } from "../../../lib/format";
import type { PanelResellerEventRow, PanelResellerSnapshotRow } from "../../../types/panel";
import { EVENT_TONE, STATUS_TONE, eventAmount, eventLabels, statusLabels } from "./labels";

export function StatusBadge({ status }: { status: string }) {
  const { t } = useTranslation();
  return <Badge tone={STATUS_TONE[status] || "muted"}>{statusLabels(t)[status] || status}</Badge>;
}

export function Detail({ label, value, ltr = false }: { label: string; value: React.ReactNode; ltr?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className={`mt-0.5 truncate text-sm text-text ${ltr ? "ltr-field" : ""}`}>{value}</dd>
    </div>
  );
}

/** Reseller history as a compact timeline; `showAccount` adds the account code for mixed feeds. */
export function EventList({
  events,
  showAccount = false,
  onOpenAccount,
}: {
  events: PanelResellerEventRow[];
  showAccount?: boolean;
  onOpenAccount?: (code: number) => void;
}) {
  const { t } = useTranslation();
  if (!events.length) return <EmptyState title={t("panel.resellerHub.eventsEmpty")} />;
  const labels = eventLabels(t);

  return (
    <ul className="divide-y divide-border/60">
      {events.map((event) => {
        const amount = eventAmount(event.data);
        return (
          <li key={event.id} className="flex items-start gap-3 py-2.5">
            <span
              className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                {
                  success: "bg-success",
                  warning: "bg-warning",
                  danger: "bg-danger",
                  primary: "bg-primary",
                  muted: "bg-muted",
                }[EVENT_TONE[event.kind] || "muted"]
              }`}
            />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span className="text-sm font-medium text-text">{labels[event.kind] || event.title}</span>
                {showAccount && event.account_code ? (
                  <button
                    type="button"
                    onClick={() => onOpenAccount?.(event.account_code as number)}
                    className="ltr-field rounded bg-surface-2 px-1.5 py-0.5 text-[11px] text-muted hover:text-primary"
                  >
                    #{event.account_code}
                  </button>
                ) : null}
                {event.actor_role && <Badge tone="muted">{event.actor_role}</Badge>}
              </div>
              <p className="mt-0.5 text-xs text-muted" title={formatUnixDate(event.created_at)}>
                {formatRelativeTime(event.created_at)}
                {event.telegram_id && showAccount ? (
                  <span className="ltr-field ms-2 inline-block">{event.telegram_id}</span>
                ) : null}
              </p>
            </div>
            {amount > 0 && <span className="shrink-0 text-sm font-semibold text-text">{formatToman(amount)}</span>}
          </li>
        );
      })}
    </ul>
  );
}

/** A small two/three-way switch for views inside a card (no shared layout animation, unlike Tabs). */
export function Segmented({
  items,
  value,
  onChange,
}: {
  items: { value: string; label: string }[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="inline-flex rounded-lg bg-surface-2 p-0.5">
      {items.map((item) => (
        <button
          key={item.value}
          type="button"
          onClick={() => onChange(item.value)}
          className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
            item.value === value ? "bg-surface text-primary shadow-sm" : "text-muted hover:text-text"
          }`}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}

/** An admin ledger row in the shape the shared ChargeItem renders. */
export function toCharge(row: PanelResellerSnapshotRow) {
  return {
    kind: row.kind,
    used_bytes: row.used_bytes,
    billed_minutes: row.billed_minutes,
    unit_price: row.unit_price,
    rate_estimated: row.rate_estimated,
    period_start: row.period_start,
    charged_at: row.snapshot_at,
    amount: row.billed_amount,
    is_debt: row.is_debt,
  };
}
