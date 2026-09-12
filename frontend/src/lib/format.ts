/** Most human-readable strings (sizes, expiry, status) already arrive pre-formatted
 * in Persian from the backend. These cover the few things the frontend renders itself. */

const tomanFormatter = new Intl.NumberFormat("fa-IR");
const dateTimeFormatter = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
  year: "numeric",
  month: "long",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

export function formatToman(amount: number): string {
  return `${tomanFormatter.format(Math.round(amount))} تومان`;
}

export function formatNumber(value: number): string {
  return tomanFormatter.format(value);
}

export function formatUnixDate(unixSeconds: number): string {
  if (!unixSeconds) return "نامشخص";
  return dateTimeFormatter.format(new Date(unixSeconds * 1000));
}

export function clampPercent(used: number, total: number): number {
  if (!total || total <= 0) return 0;
  return Math.min(100, Math.max(0, Math.round((used / total) * 100)));
}

export function copyToClipboard(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(text);
  return new Promise((resolve, reject) => {
    try {
      const el = document.createElement("textarea");
      el.value = text;
      el.style.position = "fixed";
      el.style.opacity = "0";
      document.body.appendChild(el);
      el.focus();
      el.select();
      document.execCommand("copy");
      document.body.removeChild(el);
      resolve();
    } catch (err) {
      reject(err instanceof Error ? err : new Error("copy failed"));
    }
  });
}
