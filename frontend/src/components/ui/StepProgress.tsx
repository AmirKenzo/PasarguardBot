import { useTranslation } from "react-i18next";
import { formatNumber } from "../../lib/format";

export interface StepProgressProps {
  /** Zero-based index of the current step. */
  current: number;
  total: number;
  label?: string;
}

/** Segmented progress bar with a "Step x of y · label" caption. */
export function StepProgress({ current, total, label }: StepProgressProps) {
  const { t } = useTranslation();
  return (
    <div className="space-y-1.5">
      <div className="flex gap-1">
        {Array.from({ length: total }).map((_, i) => (
          <span
            key={i}
            className={`h-1.5 flex-1 rounded-full transition-colors ${i <= current ? "bg-primary" : "bg-surface-2"}`}
          />
        ))}
      </div>
      <div className="flex items-center justify-between text-[11.5px]">
        <span className="text-muted">
          {t("ui.stepOf", { current: formatNumber(current + 1), total: formatNumber(total) })}
        </span>
        {label && <span className="font-bold text-primary">{label}</span>}
      </div>
    </div>
  );
}
