import { RefreshCw, RotateCw } from "lucide-react";
import { useTranslation } from "react-i18next";
import { IconMenuButton, MenuDivider, MenuHeader, MenuRow } from "./Menu";

export interface AutoRefreshOption {
  value: number;
  label: string;
}

export interface AutoRefreshMenuProps {
  options: AutoRefreshOption[];
  value: number;
  onChange: (value: number) => void;
  onRefreshNow: () => void;
  isRefreshing?: boolean;
}

const MENU_WIDTH = 208;
const MENU_HEIGHT_ESTIMATE = 260;

/** A small icon button that opens a dropdown to trigger an immediate refresh
 * or pick how often the list should reload itself — handy for a pending-
 * transactions queue where a new receipt should show up without a manual reload. */
export function AutoRefreshMenu({ options, value, onChange, onRefreshNow, isRefreshing }: AutoRefreshMenuProps) {
  const { t } = useTranslation();
  const activeLabel = options.find((o) => o.value === value)?.label ?? "";

  return (
    <IconMenuButton
      icon={RotateCw}
      title={t("panel.transactions.autoRefresh")}
      active={value > 0}
      badge={value > 0}
      spin={isRefreshing}
      width={MENU_WIDTH}
      heightEstimate={MENU_HEIGHT_ESTIMATE}
      align="end"
    >
      {(close) => (
        <>
          <MenuHeader
            title={t("panel.transactions.autoRefresh")}
            subtitle={t("panel.transactions.autoRefreshCurrent", { value: activeLabel })}
          />
          <MenuDivider />
          <button
            type="button"
            onClick={() => {
              onRefreshNow();
              close();
            }}
            className="flex w-full items-center gap-2 px-3 py-2 text-xs font-medium text-primary hover:bg-primary/10"
          >
            <RefreshCw size={13} />
            {t("panel.transactions.refreshNow")}
          </button>
          <MenuDivider />
          {options.map((opt) => (
            <MenuRow
              key={opt.value}
              label={opt.label}
              active={opt.value === value}
              onClick={() => {
                onChange(opt.value);
                close();
              }}
            />
          ))}
        </>
      )}
    </IconMenuButton>
  );
}
