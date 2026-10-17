import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, BetweenHorizontalStart, Send, Settings } from "lucide-react";
import { useTranslation } from "react-i18next";
import i18n from "../../../i18n";
import type { PanelHelpButton } from "../../../types/panel";
import { ButtonChip, Hint, STYLE_CLASSES } from "../keyboard/shared";
import { buttonTitle, chipStyle, KIND_ICONS, MAX_PER_ROW } from "./shared";

type Move = "up" | "down" | "before" | "after" | "own-row";

/** Returns a new layout with `id` moved, or the same layout when the move is not possible. */
export function moveInLayout(layout: number[][], id: number, move: Move): number[][] {
  const rowIndex = layout.findIndex((row) => row.includes(id));
  const source = layout[rowIndex];
  if (!source) return layout;
  const rows = layout.map((row) => [...row]);
  const row = [...source];
  rows[rowIndex] = row;
  const col = row.indexOf(id);

  if (move === "before" || move === "after") {
    const target = move === "before" ? col - 1 : col + 1;
    const other = row[target];
    if (other === undefined) return layout;
    row[target] = id;
    row[col] = other;
    return rows;
  }
  if (move === "own-row") {
    if (row.length === 1) return layout;
    row.splice(col, 1);
    rows.splice(rowIndex + 1, 0, [id]);
    return rows;
  }
  const targetIndex = move === "up" ? rowIndex - 1 : rowIndex + 1;
  const targetRow = rows[targetIndex];
  if (!targetRow) {
    // Past the edge: a lone button stays, a shared one gets a row of its own there.
    if (row.length === 1) return layout;
    row.splice(col, 1);
    if (move === "up") rows.unshift([id]);
    else rows.push([id]);
    return rows;
  }
  if (targetRow.length >= MAX_PER_ROW) return layout;
  row.splice(col, 1);
  targetRow.push(id);
  return rows.filter((r) => r.length > 0);
}

interface LayoutEditorProps {
  layout: number[][];
  buttons: Map<number, PanelHelpButton>;
  selected: number | null;
  onSelect: (id: number) => void;
  onLayoutChange: (layout: number[][]) => void;
}

export function HelpPreview({ layout, buttons }: { layout: number[][]; buttons: Map<number, PanelHelpButton> }) {
  const { t } = useTranslation();
  const rows = layout
    .map((row) => row.map((id) => buttons.get(id)).filter((b): b is PanelHelpButton => Boolean(b?.text.trim())))
    .filter((row) => row.length > 0);

  return (
    <div className="rounded-sm border border-border bg-surface-2/50 p-3">
      <div className="mb-2 flex items-center gap-1.5 text-xs text-muted">
        <Send size={13} />
        {t("panel.helpButtons.previewTitle")}
      </div>
      <div className="mb-1.5 rounded-lg bg-surface px-3 py-2 text-sm text-text shadow-sm">
        {t("panel.helpButtons.previewMessage")}
      </div>
      <div className="space-y-1">
        {rows.map((row, index) => (
          <div key={index} className="flex gap-1">
            {row.map((button) => (
              <ButtonChip
                key={button.id}
                label={button.text}
                style={chipStyle(button.style)}
                icon={button.icon != null}
                className="flex-1 basis-0"
              />
            ))}
          </div>
        ))}
        <div className="flex">
          <span className="flex flex-1 items-center justify-center gap-1 rounded-md border border-dashed border-border px-2.5 py-1.5 text-xs text-muted">
            <Settings size={12} />
            {t("panel.helpButtons.previewAdminRow")}
          </span>
        </div>
      </div>
    </div>
  );
}

export function LayoutEditor({ layout, buttons, selected, onSelect, onLayoutChange }: LayoutEditorProps) {
  const { t } = useTranslation();
  const rtl = i18n.dir() === "rtl";
  const move = (direction: Move) => {
    if (selected == null) return;
    onLayoutChange(moveInLayout(layout, selected, direction));
  };
  // "Before" is the start side of the row: right in RTL, left in LTR.
  const StartIcon = rtl ? ArrowRight : ArrowLeft;
  const EndIcon = rtl ? ArrowLeft : ArrowRight;
  const tools: { key: Move; icon: typeof ArrowUp; label: string }[] = [
    { key: "up", icon: ArrowUp, label: t("panel.helpButtons.moveUp") },
    { key: "down", icon: ArrowDown, label: t("panel.helpButtons.moveDown") },
    { key: "before", icon: StartIcon, label: t("panel.helpButtons.moveBefore") },
    { key: "after", icon: EndIcon, label: t("panel.helpButtons.moveAfter") },
    { key: "own-row", icon: BetweenHorizontalStart, label: t("panel.helpButtons.moveOwnRow") },
  ];

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Hint>{t("panel.helpButtons.rowsHint")}</Hint>
        <div className="flex gap-1">
          {tools.map(({ key, icon: Icon, label }) => (
            <button
              key={key}
              type="button"
              title={label}
              aria-label={label}
              disabled={selected == null}
              onClick={() => move(key)}
              className="flex h-8 w-8 items-center justify-center rounded-md border border-border text-text transition-colors hover:bg-surface-2 disabled:opacity-40"
            >
              <Icon size={15} />
            </button>
          ))}
        </div>
      </div>

      {layout.length === 0 && <Hint>{t("panel.helpButtons.noButtons")}</Hint>}
      {layout.map((row, rowIndex) => (
        <div key={rowIndex} className="flex items-stretch gap-1.5 rounded-md border border-dashed border-border p-1.5">
          <span className="flex w-5 shrink-0 items-center justify-center text-2xs text-muted">{rowIndex + 1}</span>
          <div className="flex min-w-0 flex-1 gap-1.5">
            {row.map((id) => {
              const button = buttons.get(id);
              if (!button) return null;
              const Icon = KIND_ICONS[button.kind];
              const incomplete = !button.text.trim() || (button.kind === "link" && !button.url);
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => onSelect(id)}
                  className={`flex min-w-0 flex-1 basis-0 items-center justify-center gap-1.5 rounded-md border px-2 py-2 text-xs font-medium transition-shadow ${
                    selected === id ? "ring-2 ring-primary ring-offset-1 ring-offset-surface" : ""
                  } ${incomplete ? "border-warning/50 bg-warning/10 text-warning" : STYLE_CLASSES[chipStyle(button.style)]}`}
                >
                  <Icon size={13} className="shrink-0" />
                  <span dir="auto" className="truncate">
                    {buttonTitle(button, t("panel.helpButtons.untitled"))}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

