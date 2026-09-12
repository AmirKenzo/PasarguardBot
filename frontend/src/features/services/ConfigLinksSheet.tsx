import { Link2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Sheet } from "../../components/ui/Sheet";
import { Spinner } from "../../components/ui/Spinner";
import { configLinksFromUrls } from "../../lib/serviceHelpers";
import { copyToClipboard } from "../../lib/format";
import { useConfigLinksQuery } from "../../queries/useServices";
import type { WebAppConfigLinkItem } from "../../types/webapp";

export interface ConfigLinksSheetProps {
  open: boolean;
  onClose: () => void;
  code: number;
  username: string;
  fallbackLinks?: string[];
}

export function ConfigLinksSheet({ open, onClose, code, username, fallbackLinks }: ConfigLinksSheetProps) {
  const { data, isLoading, error } = useConfigLinksQuery(code, open);
  const [copied, setCopied] = useState<number | null>(null);
  const [links, setLinks] = useState<WebAppConfigLinkItem[]>([]);

  useEffect(() => {
    if (!open) return;
    if (data?.links?.length) {
      setLinks(data.links);
      return;
    }
    const fallback = configLinksFromUrls(fallbackLinks ?? []);
    setLinks(fallback);
  }, [open, data?.links, fallbackLinks]);

  return (
    <Sheet open={open} onClose={onClose} title="لینک‌های کانفیگ">
      <p className="mb-3 text-xs text-muted">
        {username} · روی هر کانفیگ بزن تا لینک کپی شود
      </p>
      {error && <p className="mb-3 text-sm text-danger">{(error as Error).message}</p>}
      {isLoading ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : links.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted">لینکی یافت نشد</p>
      ) : (
        <div className="max-h-[55vh] space-y-2 overflow-y-auto pr-0.5">
          {links.map((item) => (
            <button
              key={item.index}
              type="button"
              onClick={() => {
                void copyToClipboard(item.url).then(() => {
                  setCopied(item.index);
                  window.setTimeout(() => setCopied((c) => (c === item.index ? null : c)), 1600);
                });
              }}
              className={`flex w-full items-center gap-3 rounded-md border px-3.5 py-3 text-right transition ${
                copied === item.index
                  ? "border-success/40 bg-success/10"
                  : "border-border bg-surface hover:border-primary/35 hover:bg-primary/5"
              }`}
            >
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                <Link2 size={16} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-text">{item.name}</p>
                <p className="mt-0.5 text-[11px] text-muted">
                  {copied === item.index ? "کپی شد ✓" : "کلیک = کپی لینک"}
                </p>
              </div>
            </button>
          ))}
        </div>
      )}
    </Sheet>
  );
}
