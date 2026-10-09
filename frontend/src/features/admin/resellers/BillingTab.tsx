import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Button, ErrorState, Input, Pagination } from "../../../components/ui";
import { panelResellersApi } from "../../../api/panel";
import { formatNumber, formatToman } from "../../../lib/format";
import { ChargeItem } from "../../../components/ChargeItem";
import { toCharge } from "./parts";
import { usePanelQuery } from "../../../queries/usePanelApi";
import { SectionCard, SelectField, Toolbar } from "../components";
import { EventList, Segmented } from "./parts";
import { eventLabels } from "./labels";

const RANGES: Record<string, number> = { day: 86400, week: 7 * 86400, month: 30 * 86400, all: 0 };

interface Filters {
  account: string;
  telegram: string;
  range: string;
  kind: string;
}

export default function BillingTab() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const view = searchParams.get("view") === "events" ? "events" : "ledger";
  const initial: Filters = {
    account: searchParams.get("account") || "",
    telegram: searchParams.get("telegram") || "",
    range: "month",
    kind: "",
  };
  const [filters, setFilters] = useState<Filters>(initial);
  const [draft, setDraft] = useState<Filters>(initial);
  const [page, setPage] = useState(1);

  const setView = (value: string) => {
    setPage(1);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("view", value);
      return next;
    });
  };

  const accountCode = Number(filters.account) || null;
  const telegramId = Number(filters.telegram) || null;
  const rangeSeconds = RANGES[filters.range] ?? 0;
  const since = rangeSeconds ? Math.floor(Date.now() / 1000) - rangeSeconds : null;

  const ledger = usePanelQuery(
    ["reseller-ledger", filters, page],
    (auth) =>
      panelResellersApi.getLedger({
        ...auth,
        account_code: accountCode,
        telegram_id: telegramId,
        since,
        page,
        limit: 25,
      }),
    { enabled: view === "ledger" }
  );
  const events = usePanelQuery(
    ["reseller-events", filters, page],
    (auth) =>
      panelResellersApi.listEvents({
        ...auth,
        account_code: accountCode,
        telegram_id: telegramId,
        kinds: filters.kind ? [filters.kind] : [],
        page,
        limit: 25,
      }),
    { enabled: view === "events" }
  );

  const labels = eventLabels(t);
  const active = view === "ledger" ? ledger : events;
  const totalPages = (view === "ledger" ? ledger.data?.meta.total_pages : events.data?.meta.total_pages) || 1;

  return (
    <>
      <div className="mb-3">
        <Segmented
          items={[
            { value: "ledger", label: t("panel.resellerHub.billing.ledger") },
            { value: "events", label: t("panel.resellerHub.billing.events") },
          ]}
          value={view}
          onChange={setView}
        />
      </div>

      <Toolbar
        onSubmit={() => {
          setPage(1);
          setFilters(draft);
        }}
      >
        <div className="w-32">
          <Input
            label={t("panel.resellerHub.billing.accountCode")}
            ltr
            inputMode="numeric"
            value={draft.account}
            onChange={(event) => setDraft((prev) => ({ ...prev, account: event.target.value.replace(/\D/g, "") }))}
          />
        </div>
        <div className="w-40">
          <Input
            label={t("panel.resellers.telegramUser")}
            ltr
            inputMode="numeric"
            value={draft.telegram}
            onChange={(event) => setDraft((prev) => ({ ...prev, telegram: event.target.value.replace(/\D/g, "") }))}
          />
        </div>
        {view === "ledger" ? (
          <div className="w-36">
            <SelectField
              label={t("panel.resellerHub.billing.range")}
              options={[
                { value: "day", label: t("panel.resellerHub.billing.rangeDay") },
                { value: "week", label: t("panel.resellerHub.billing.rangeWeek") },
                { value: "month", label: t("panel.resellerHub.billing.rangeMonth") },
                { value: "all", label: t("panel.common.all") },
              ]}
              value={draft.range}
              onChange={(event) => setDraft((prev) => ({ ...prev, range: event.target.value }))}
            />
          </div>
        ) : (
          <div className="w-44">
            <SelectField
              label={t("panel.resellerHub.billing.kind")}
              options={[
                { value: "", label: t("panel.common.all") },
                ...(events.data?.kinds || []).map((kind) => ({ value: kind, label: labels[kind] || kind })),
              ]}
              value={draft.kind}
              onChange={(event) => setDraft((prev) => ({ ...prev, kind: event.target.value }))}
            />
          </div>
        )}
        <Button size="md" type="submit" variant="secondary">
          {t("panel.common.applyFilter")}
        </Button>
      </Toolbar>

      {active.isError ? (
        <ErrorState message={active.error.message} onRetry={() => void active.refetch()} />
      ) : view === "ledger" ? (
        <SectionCard
          title={t("panel.resellerHub.billing.ledger")}
          description={t("panel.resellerHub.billing.ledgerHint")}
          actions={
            ledger.data ? (
              <div className="text-end">
                <p className="text-[11px] text-muted">{t("panel.resellerHub.billing.totalBilled")}</p>
                <p className="text-sm font-bold text-text">{formatToman(ledger.data.total_billed)}</p>
              </div>
            ) : undefined
          }
        >
          {ledger.isLoading ? (
            <p className="py-8 text-center text-sm text-muted">{t("reseller.loading")}</p>
          ) : ledger.data?.rows.length ? (
            <ul className="grid gap-2.5 lg:grid-cols-2">
              {ledger.data.rows.map((row) => (
                <ChargeItem
                  key={row.id}
                  charge={toCharge(row)}
                  panelCounter={row.used_traffic}
                  account={`${row.username || t("panel.resellerHub.billing.deleted")} · #${row.account_code}`}
                />
              ))}
            </ul>
          ) : (
            <p className="py-8 text-center text-sm text-muted">{t("panel.resellers.invoicesEmpty")}</p>
          )}
        </SectionCard>
      ) : (
        <SectionCard
          title={t("panel.resellerHub.billing.events")}
          description={
            events.data ? t("panel.resellerHub.billing.eventCount", { count: formatNumber(events.data.meta.total) }) : undefined
          }
        >
          <EventList
            events={events.data?.events || []}
            showAccount
            onOpenAccount={(code) => setDraft((prev) => ({ ...prev, account: String(code) }))}
          />
        </SectionCard>
      )}

      <div className="mt-4">
        <Pagination page={page} totalPages={totalPages} onChange={setPage} />
      </div>
    </>
  );
}
