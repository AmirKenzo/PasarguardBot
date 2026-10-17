import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Badge } from "../../../components/ui";
import type { ThemePackItem } from "../../../types/panel";
import { sectionLabels } from "../keyboard/shared";
import { isApplicable, issueLabel, statusLabels, statusTone } from "./shared";

export interface PreviewListProps {
  items: ThemePackItem[];
  selected: Set<string>;
  onChange: (next: Set<string>) => void;
}

function ItemRow({
  item,
  checked,
  onToggle,
}: {
  item: ThemePackItem;
  checked: boolean;
  onToggle: (on: boolean) => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const applicable = isApplicable(item);
  const showDiff = item.status !== "unknown" && (item.incoming != null || item.current != null);

  return (
    <li className="px-3 py-2.5">
      <div className="flex items-start gap-2.5">
        <input
          type="checkbox"
          className="mt-1 h-4 w-4 accent-primary"
          checked={checked}
          disabled={!applicable}
          onChange={(event) => onToggle(event.target.checked)}
          aria-label={item.title}
        />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="truncate text-sm text-text">{item.title}</span>
            {item.lang && (
              <span className="ltr-field rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] uppercase text-muted">
                {item.lang}
              </span>
            )}
            <Badge tone={statusTone[item.status] ?? "muted"}>{statusLabels(t)[item.status] ?? item.status}</Badge>
          </div>
          {(item.errors.length > 0 || item.warnings.length > 0) && (
            <div className="mt-1 flex flex-wrap gap-1">
              {item.errors.map((code) => (
                <span key={code} className="rounded-md bg-danger/12 px-1.5 py-0.5 text-[11px] text-danger">
                  {issueLabel(t, code)}
                </span>
              ))}
              {item.warnings.map((code) => (
                <span key={code} className="rounded-md bg-warning/12 px-1.5 py-0.5 text-[11px] text-warning">
                  {issueLabel(t, code)}
                </span>
              ))}
            </div>
          )}
          {showDiff && (
            <button
              type="button"
              onClick={() => setOpen((value) => !value)}
              className="mt-1 inline-flex items-center gap-1 text-xs text-primary"
            >
              <ChevronDown size={13} className={`transition-transform ${open ? "rotate-180" : ""}`} />
              {open ? t("panel.themePacks.hideCompare") : t("panel.themePacks.showCompare")}
            </button>
          )}
          {open && (
            <div className="mt-2 grid gap-2 md:grid-cols-2">
              <div>
                <p className="mb-1 text-[11px] font-semibold text-muted">{t("panel.themePacks.currentValue")}</p>
                <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words rounded-lg font-sans bg-surface-2 p-2 text-xs leading-relaxed text-text">
                  {item.current || "—"}
                </pre>
              </div>
              <div>
                <p className="mb-1 text-[11px] font-semibold text-muted">{t("panel.themePacks.incomingValue")}</p>
                <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words rounded-lg font-sans bg-primary/8 p-2 text-xs leading-relaxed text-text">
                  {item.incoming || "—"}
                </pre>
              </div>
            </div>
          )}
        </div>
      </div>
    </li>
  );
}

export function PreviewList({ items, selected, onChange }: PreviewListProps) {
  const { t } = useTranslation();
  const buttonSections = sectionLabels(t);
  const groups = [
    { key: "text", label: t("panel.themePacks.texts"), items: items.filter((item) => item.kind === "text") },
    { key: "button", label: t("panel.themePacks.buttons"), items: items.filter((item) => item.kind === "button") },
    { key: "layout", label: t("panel.themePacks.layout"), items: items.filter((item) => item.kind === "layout") },
  ].filter((group) => group.items.length > 0);

  const setOne = (id: string, on: boolean) => {
    const next = new Set(selected);
    if (on) next.add(id);
    else next.delete(id);
    onChange(next);
  };

  return (
    <div className="flex flex-col gap-2.5">
      {groups.map((group) => (
        <div key={group.key} className="rounded-xl border border-border">
          <p className="border-b border-border bg-surface-2/60 px-3 py-2 text-sm font-semibold text-text">
            {group.label} <span className="font-normal text-muted">({group.items.length})</span>
          </p>
          <ul className="divide-y divide-border">
            {group.items.map((item) => (
              <ItemRow
                key={item.id}
                item={
                  item.kind === "button" ? { ...item, title: `${item.title} · ${buttonSections[item.section] ?? item.section}` } : item
                }
                checked={selected.has(item.id)}
                onToggle={(on) => setOne(item.id, on)}
              />
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
