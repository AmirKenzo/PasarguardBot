import { useEffect, useState } from "react";
import { useAuth } from "../../../context/AuthContext";

function decodeTokenExpiry(token: string | null): number | null {
  if (!token) return null;
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  const exp = Number(parts[1]);
  return Number.isFinite(exp) && exp > 0 ? exp : null;
}

function formatClock(expiresAt: number): string {
  const secondsLeft = Math.max(0, Math.round(expiresAt - Date.now() / 1000));
  const h = Math.floor(secondsLeft / 3600);
  const m = Math.floor((secondsLeft % 3600) / 60);
  const s = secondsLeft % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}

/** A tiny rotated tab on the left edge, out of the way of everything else. */
export function SessionExpiry() {
  const { sessionToken } = useAuth();
  const expiresAt = decodeTokenExpiry(sessionToken);
  const [dismissed, setDismissed] = useState(false);
  const [label, setLabel] = useState(() => (expiresAt ? formatClock(expiresAt) : ""));

  useEffect(() => {
    if (!expiresAt) return;
    setLabel(formatClock(expiresAt));
    const id = setInterval(() => setLabel(formatClock(expiresAt)), 1000);
    return () => clearInterval(id);
  }, [expiresAt]);

  if (!expiresAt || dismissed) return null;

  return (
    <button
      type="button"
      dir="ltr"
      onClick={() => setDismissed(true)}
      title={label}
      style={{ writingMode: "vertical-rl" }}
      className="fixed bottom-24 left-0 z-40 rounded-r-md border border-warning/30 bg-warning/15 px-1 py-2 text-[10px] font-medium tracking-tight text-warning"
    >
      {label}
    </button>
  );
}
