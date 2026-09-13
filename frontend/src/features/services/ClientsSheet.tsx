import { Copy, Fingerprint, Network, Smartphone } from "lucide-react";
import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Sheet } from "../../components/ui/Sheet";
import { Spinner } from "../../components/ui/Spinner";
import { copyToClipboard, formatRelativeTime } from "../../lib/format";
import { useServiceClientsQuery } from "../../queries/useServices";
import type { WebAppClientItem } from "../../types/webapp";

function platformTone(platform?: string | null): string {
  const p = (platform || "").toLowerCase();
  if (p.includes("android")) return "bg-success/12 text-success ring-success/25";
  if (p.includes("ios") || p.includes("iphone")) return "bg-accent/12 text-accent ring-accent/25";
  if (p.includes("windows")) return "bg-primary/12 text-primary ring-primary/25";
  if (p.includes("mac")) return "bg-primary/12 text-primary ring-primary/25";
  return "bg-warning/12 text-warning ring-warning/25";
}

function CopyRow({ label, value, icon }: { label: string; value?: string | null; icon: ReactNode }) {
  const [copied, setCopied] = useState(false);
  if (!value) return null;

  return (
    <div className="flex items-center gap-2 rounded-md bg-surface-2 px-3 py-2.5 ring-1 ring-border">
      <div className="text-muted">{icon}</div>
      <div className="min-w-0 flex-1">
        <p className="text-[10px] text-muted">{label}</p>
        <p className="truncate font-mono text-xs text-text" dir="ltr">
          {value}
        </p>
      </div>
      <button
        type="button"
        onClick={() => {
          void copyToClipboard(value).then(() => {
            setCopied(true);
            window.setTimeout(() => setCopied(false), 1500);
          });
        }}
        className="shrink-0 rounded-md p-1.5 text-muted transition hover:bg-surface hover:text-primary"
      >
        {copied ? <span className="text-[10px] text-success">✓</span> : <Copy size={14} />}
      </button>
    </div>
  );
}

export interface ClientsSheetProps {
  open: boolean;
  onClose: () => void;
  code: number;
  username: string;
}

export function ClientsSheet({ open, onClose, code, username }: ClientsSheetProps) {
  const { t } = useTranslation();
  const { data, isLoading, error } = useServiceClientsQuery(code, open);
  const clients: WebAppClientItem[] = data?.clients ?? [];

  return (
    <Sheet open={open} onClose={onClose} title={t("clients.title")}>
      <p className="mb-3 text-xs text-muted">
        {username} · {t("clients.connectedDevices", { count: clients.length })}
      </p>
      {error && <p className="mb-3 text-sm text-danger">{(error as Error).message}</p>}
      {isLoading ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : clients.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted">{t("clients.noClients")}</p>
      ) : (
        <div className="max-h-[55vh] space-y-3 overflow-y-auto pr-0.5">
          {clients.map((client, idx) => (
            <div key={`${client.created_at}-${idx}`} className="rounded-md border border-border bg-surface p-3.5">
              <div className="mb-3 flex items-center gap-2.5">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                  <Smartphone size={17} />
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-bold text-text">{client.app_name || t("common.unknown")}</p>
                  <p className="text-[11px] text-muted">{formatRelativeTime(client.created_at)}</p>
                </div>
              </div>
              <div className="mb-3 flex flex-wrap gap-1.5">
                {client.version && (
                  <span className="rounded-full bg-warning/12 px-2 py-0.5 text-[10px] font-medium text-warning ring-1 ring-warning/20">
                    v{client.version}
                  </span>
                )}
                {client.platform && (
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ring-1 ${platformTone(client.platform)}`}>
                    {client.platform}
                  </span>
                )}
              </div>
              <div className="space-y-2">
                <CopyRow label={t("clients.ipAddress")} value={client.ip_address} icon={<Network size={15} />} />
                <CopyRow label={t("clients.hwid")} value={client.hwid} icon={<Fingerprint size={15} />} />
              </div>
            </div>
          ))}
        </div>
      )}
    </Sheet>
  );
}
