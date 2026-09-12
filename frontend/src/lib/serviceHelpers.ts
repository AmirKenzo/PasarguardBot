type BadgeTone = "success" | "warning" | "danger" | "muted";

export function expiryParts(expirationTime: string): { remaining: string; date: string } {
  if (!expirationTime || expirationTime === "نامشخص") {
    return { remaining: "نامشخص", date: "نامشخص" };
  }
  const parenIdx = expirationTime.indexOf("(");
  if (parenIdx === -1) {
    return { date: expirationTime.trim(), remaining: "—" };
  }
  return {
    date: expirationTime.slice(0, parenIdx).trim(),
    remaining: expirationTime.slice(parenIdx + 1).replace(/\)\s*$/, "").trim(),
  };
}

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
