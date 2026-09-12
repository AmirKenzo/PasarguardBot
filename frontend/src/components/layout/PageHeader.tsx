import type { ReactNode } from "react";
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronRight } from "lucide-react";
import { useTelegram } from "../../hooks/useTelegram";

export interface PageHeaderProps {
  title: string;
  subtitle?: string;
  back?: string | (() => void);
  action?: ReactNode;
}

export function PageHeader({ title, subtitle, back, action }: PageHeaderProps) {
  const navigate = useNavigate();
  const { showBackButton } = useTelegram();

  const goBack = () => {
    if (typeof back === "function") back();
    else if (back) navigate(back);
    else navigate(-1);
  };

  useEffect(() => {
    if (!back) return;
    return showBackButton(goBack);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [back]);

  return (
    <div className="mb-4 flex items-center gap-3">
      {back && (
        <button
          onClick={goBack}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-border bg-surface text-text"
          aria-label="بازگشت"
        >
          <ChevronRight size={19} />
        </button>
      )}
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-lg font-bold text-text">{title}</h1>
        {subtitle && <p className="truncate text-xs text-muted">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
