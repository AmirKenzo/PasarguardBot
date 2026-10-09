import { useTranslation } from "react-i18next";
import { Badge } from "./ui";
import { formatBytes, formatToman } from "../lib/format";
import { chargeFormula, chargePeriod, chargeRate, chargeUsage } from "../lib/resellerCharges";
import type { ChargeLike } from "../lib/resellerCharges";

export interface ChargeItemProps {
  charge: ChargeLike & { amount: number; is_debt?: boolean };
  /** Panel's cumulative traffic counter at charge time; shown to admins. */
  panelCounter?: number;
  /** Account label for mixed-account lists. */
  account?: string;
}

/** One reseller charge: period, what was used, the rate, the calculation and the amount. */
export function ChargeItem({ charge, panelCounter, account }: ChargeItemProps) {
  const { t } = useTranslation();
  return (
    <li className="rounded-lg border border-border bg-surface p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge tone={charge.kind === "hourly" ? "primary" : "muted"}>
              {t(charge.kind === "hourly" ? "reseller.charge.hourly" : "reseller.charge.usage")}
            </Badge>
            {charge.is_debt && <Badge tone="danger">{t("reseller.charge.debt")}</Badge>}
            {account && <span className="ltr-field truncate text-xs font-semibold text-text">{account}</span>}
          </div>
          <p className="mt-1 text-[11px] text-muted">{chargePeriod(t, charge)}</p>
        </div>
        <p className="shrink-0 text-sm font-extrabold text-text">{formatToman(charge.amount)}</p>
      </div>
      <dl className="mt-2.5 grid grid-cols-2 gap-2 border-t border-border/60 pt-2.5 text-xs sm:grid-cols-3">
        <div>
          <dt className="text-muted">{t(charge.kind === "hourly" ? "reseller.charge.activeTime" : "reseller.charge.used")}</dt>
          <dd className="mt-0.5 font-semibold text-text">{chargeUsage(t, charge)}</dd>
        </div>
        <div>
          <dt className="text-muted">{t("reseller.charge.rate")}</dt>
          <dd className="mt-0.5 font-semibold text-text">{chargeRate(t, charge)}</dd>
        </div>
        <div className="col-span-2 sm:col-span-1">
          <dt className="text-muted">{t("reseller.charge.calculation")}</dt>
          <dd className="mt-0.5 font-semibold text-text">
            {chargeFormula(t, charge)} = {formatToman(charge.amount)}
          </dd>
        </div>
      </dl>
      {panelCounter != null && charge.kind !== "hourly" && (
        <p className="mt-2 text-[11px] text-muted">
          {t("reseller.charge.panelCounter", { value: formatBytes(panelCounter, 2) })}
        </p>
      )}
    </li>
  );
}
