import i18n from "../i18n";
import { formatBytes } from "./format";

type BadgeTone = "success" | "warning" | "danger" | "muted";

export function statusTone(status: string | null): { icon: string; chip: string; badge: BadgeTone } {
  const key = (status || "").toLowerCase();
  if (key === "active") {
    return {
      icon: "bg-success/12 text-success ring-1 ring-success/25",
      chip: "bg-success/12 text-success",
      badge: "success",
    };
  }
  if (key === "expired" || key === "disabled") {
    return {
      icon: "bg-danger/12 text-danger ring-1 ring-danger/25",
      chip: "bg-danger/12 text-danger",
      badge: "danger",
    };
  }
  if (key === "limited" || key === "on_hold") {
    return {
      icon: "bg-warning/12 text-warning ring-1 ring-warning/25",
      chip: "bg-warning/12 text-warning",
      badge: "warning",
    };
  }
  return {
    icon: "bg-surface-2 text-muted ring-1 ring-border",
    chip: "bg-surface-2 text-muted",
    badge: "muted",
  };
}

export function transactionTypeLabel(typeKey: string, currency?: string | null): string {
  if (typeKey === "crypto") return i18n.t("transaction.crypto", { currency: currency || "" });
  return i18n.t(`transaction.${typeKey}`, i18n.t("transaction.manual_card"));
}

export function statusLabel(status: string | null): string {
  const key = (status || "").toLowerCase();
  const known = ["active", "expired", "limited", "disabled", "on_hold"];
  if (known.includes(key)) return i18n.t(`serviceStatus.${key}`);
  return status || i18n.t("common.unknown");
}

/** Bilingual plan/volume label, replacing the backend's Persian-only convert_storage(). */
export function formatPlanLabel(
  storageGb: number,
  planType?: string | null,
  resetStrategy?: string | null,
  forButton = false
): string {
  const t = i18n.t.bind(i18n);
  const volumeText = formatBytes(storageGb * 1024 ** 3, storageGb < 1 ? 0 : 2);

  if (planType === "unlimited_volume") {
    return forButton ? t("planLabel.unlimited") : t("planLabel.fairUsage", { volume: volumeText });
  }

  if (resetStrategy && resetStrategy !== "no_reset") {
    const knownStrategies = ["day", "week", "month", "year"];
    const period = knownStrategies.includes(resetStrategy) ? t(`resetStrategy.${resetStrategy}`) : t("planLabel.unlimited");
    return `${period} ${volumeText}`;
  }

  if (planType === "fair_usage" || planType === "fair") {
    return t("planLabel.fairUsage", { volume: volumeText });
  }

  return volumeText;
}

export function configLinksFromUrls(urls: string[]): { index: number; name: string; url: string }[] {
  return urls
    .map((raw, index) => {
      const url = raw.trim();
      if (!url) return null;
      let name = `Config ${index + 1}`;
      if (url.includes("#")) {
        const hashIdx = url.lastIndexOf("#");
        const fragment = hashIdx >= 0 ? url.slice(hashIdx + 1) : "";
        try {
          const decoded = decodeURIComponent(fragment).trim();
          if (decoded) name = decoded;
        } catch {
          if (fragment.trim()) name = fragment.trim();
        }
      }
      return { index, name, url };
    })
    .filter((item): item is { index: number; name: string; url: string } => item !== null);
}
