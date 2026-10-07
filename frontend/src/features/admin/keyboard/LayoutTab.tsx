import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  closestCenter,
  DndContext,
  pointerWithin,
  DragOverlay,
  KeyboardSensor,
  MouseSensor,
  TouchSensor,
  useDroppable,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import type { CollisionDetection, DragEndEvent, DragOverEvent, DragStartEvent } from "@dnd-kit/core";
import {
  arrayMove,
  horizontalListSortingStrategy,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  AlertTriangle,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  ChevronDown,
  Eye,
  EyeOff,
  GripVertical,
  Pencil,
  Plus,
  RotateCcw,
  Send,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "../../../components/ui";
import type { PanelKeyboardButton, PanelKeyboardResponse } from "../../../types/panel";
import { ConfirmButton } from "../components";
import { blockedLabels, ButtonChip, buttonLabel, Hint, renderedStyle } from "./shared";

export interface LayoutRow {
  id: string;
  keys: string[];
}

let rowSeq = 0;
export const newRowId = () => `kb-row-${++rowSeq}`;
export const toRows = (layout: string[][]): LayoutRow[] => layout.map((keys) => ({ id: newRowId(), keys: [...keys] }));

const NEW_ROW_ZONE = "kb-new-row";

type Direction = "up" | "down" | "start" | "end";

interface LayoutTabProps {
  data: PanelKeyboardResponse;
  rows: LayoutRow[];
  hidden: string[];
  onRowsChange: (rows: LayoutRow[]) => void;
  onHiddenChange: (hidden: string[]) => void;
  onEditButton: (key: string) => void;
  onReset: () => void;
  resetting: boolean;
}

export function LayoutTab({
  data,
  rows,
  hidden,
  onRowsChange,
  onHiddenChange,
  onEditButton,
  onReset,
  resetting,
}: LayoutTabProps) {
  const { t } = useTranslation();
  const [selected, setSelected] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [dragSourceRow, setDragSourceRow] = useState<string | null>(null);
  const [overId, setOverId] = useState<string | null>(null);

  const buttonsByKey = useMemo(
    () => new Map<string, PanelKeyboardButton>(data.buttons.map((button) => [button.key, button])),
    [data.buttons]
  );
  const rowIds = rows.map((row) => row.id);
  const isRowId = (id: string) => rowIds.includes(id);
  const rowOf = (id: string) => rows.find((row) => row.id === id || row.keys.includes(id));

  // Touch needs a short press so the page can still scroll under a finger.
  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 5 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 180, tolerance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  // Rows only collide with rows. A button prefers the button or zone under the
  // pointer, then the row under it (drop at its end), then the nearest button.
  const collisionDetection: CollisionDetection = (args) => {
    const rowTargets = args.droppableContainers.filter((container) => isRowId(String(container.id)));
    if (isRowId(String(args.active.id))) return closestCenter({ ...args, droppableContainers: rowTargets });
    const buttonTargets = args.droppableContainers.filter((container) => !isRowId(String(container.id)));
    const underPointer = pointerWithin({ ...args, droppableContainers: buttonTargets });
    if (underPointer.length > 0) return underPointer;
    const rowUnderPointer = pointerWithin({ ...args, droppableContainers: rowTargets });
    if (rowUnderPointer.length > 0) return rowUnderPointer;
    return closestCenter({ ...args, droppableContainers: buttonTargets });
  };

  const toggleHidden = (key: string) =>
    onHiddenChange(hidden.includes(key) ? hidden.filter((item) => item !== key) : [...hidden, key]);

  function move(key: string, direction: Direction) {
    const rowIndex = rows.findIndex((row) => row.keys.includes(key));
    const row = rows[rowIndex];
    if (!row) return;
    const position = row.keys.indexOf(key);
    const next = rows.map((item) => ({ ...item, keys: [...item.keys] }));
    const current = next[rowIndex]!;
    if (direction === "start" || direction === "end") {
      const target = direction === "start" ? position - 1 : position + 1;
      if (target < 0 || target >= current.keys.length) return;
      current.keys = arrayMove(current.keys, position, target);
    } else {
      current.keys.splice(position, 1);
      const targetIndex = direction === "up" ? rowIndex - 1 : rowIndex + 1;
      if (targetIndex < 0) next.unshift({ id: newRowId(), keys: [key] });
      else if (targetIndex >= next.length) next.push({ id: newRowId(), keys: [key] });
      else next[targetIndex]!.keys.push(key);
    }
    onRowsChange(next.filter((item) => item.keys.length > 0 || item.id !== row.id));
  }

  function handleDragStart(event: DragStartEvent) {
    const id = String(event.active.id);
    setActiveId(id);
    setDragSourceRow(isRowId(id) ? null : (rowOf(id)?.id ?? null));
    if (!isRowId(id)) setSelected(id);
  }

  // Only track the target while dragging. Moving the button mid-drag reshapes
  // the rows under the pointer and can bounce it between rows forever.
  function handleDragOver({ over }: DragOverEvent) {
    setOverId(over ? String(over.id) : null);
  }

  function clearDrag() {
    setActiveId(null);
    setDragSourceRow(null);
    setOverId(null);
  }

  function handleDragEnd({ active, over }: DragEndEvent) {
    const activeKey = String(active.id);
    const source = dragSourceRow;
    clearDrag();
    if (!over) return;
    const overId = String(over.id);

    if (isRowId(activeKey)) {
      const from = rowIds.indexOf(activeKey);
      const to = rowIds.indexOf(overId);
      if (from >= 0 && to >= 0 && from !== to) onRowsChange(arrayMove(rows, from, to));
      return;
    }

    let next = rows;
    if (overId === NEW_ROW_ZONE) {
      next = [
        ...rows.map((row) => ({ ...row, keys: row.keys.filter((key) => key !== activeKey) })),
        { id: newRowId(), keys: [activeKey] },
      ];
    } else {
      const from = rowOf(activeKey);
      const to = rowOf(overId);
      if (!from || !to) return;
      if (from.id === to.id) {
        const fromIndex = from.keys.indexOf(activeKey);
        const toIndex = to.keys.indexOf(overId);
        if (toIndex >= 0 && fromIndex !== toIndex) {
          next = rows.map((row) => (row.id === from.id ? { ...row, keys: arrayMove(row.keys, fromIndex, toIndex) } : row));
        }
      } else {
        const overIndex = to.keys.indexOf(overId);
        next = rows.map((row) => {
          if (row.id === from.id) return { ...row, keys: row.keys.filter((key) => key !== activeKey) };
          if (row.id !== to.id) return row;
          const keys = [...row.keys];
          keys.splice(overIndex >= 0 ? overIndex : keys.length, 0, activeKey);
          return { ...row, keys };
        });
      }
    }
    // Drop the row the button came from only if dragging emptied it.
    onRowsChange(next.filter((row) => row.keys.length > 0 || row.id !== source));
  }

  const selectedButton = selected ? buttonsByKey.get(selected) : undefined;
  const selectedHidden = selected ? hidden.includes(selected) : false;
  const activeIsRow = activeId ? isRowId(activeId) : false;
  // Row a dragged button would land in, when it is not the row it came from.
  const targetRowId =
    activeId && !activeIsRow && overId && overId !== NEW_ROW_ZONE ? (rowOf(overId)?.id ?? null) : null;
  const crossRowTarget = targetRowId && targetRowId !== dragSourceRow ? targetRowId : null;

  const editor = (
    <div className="rounded-xl border border-border bg-surface p-3 sm:p-4">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-text">{t("panel.keyboard.mainMenuLayout")}</h2>
          <Hint>{t("panel.keyboard.dragHint")}</Hint>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Button size="sm" variant="ghost" onClick={() => onRowsChange([...rows, { id: newRowId(), keys: [] }])}>
            <Plus size={15} />
            {t("panel.keyboard.emptyRow")}
          </Button>
          <ConfirmButton
            size="sm"
            variant="ghost"
            loading={resetting}
            message={t("panel.keyboard.resetConfirm")}
            onConfirm={onReset}
          >
            <RotateCcw size={14} />
            {t("panel.common.restoreDefaults")}
          </ConfirmButton>
        </div>
      </div>

      <DndContext
        sensors={sensors}
        collisionDetection={collisionDetection}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={handleDragEnd}
        onDragCancel={clearDrag}
      >
        <SortableContext items={rowIds} strategy={verticalListSortingStrategy}>
          <div className="space-y-2">
            {rows.map((row, index) => (
              <SortableRow
                key={row.id}
                id={row.id}
                index={index}
                empty={row.keys.length === 0}
                dropTarget={crossRowTarget === row.id}
                emptyLabel={t("panel.keyboard.emptyRowHint")}
              >
                <SortableContext items={row.keys} strategy={horizontalListSortingStrategy}>
                  {row.keys.map((key) => (
                    <SortableChip
                      key={key}
                      id={key}
                      label={buttonLabel(buttonsByKey.get(key), key)}
                      hidden={hidden.includes(key)}
                      blocked={Boolean(buttonsByKey.get(key)?.blocked)}
                      selected={selected === key}
                      insertBefore={crossRowTarget === row.id && overId === key}
                      onSelect={() => setSelected(selected === key ? null : key)}
                    />
                  ))}
                </SortableContext>
              </SortableRow>
            ))}
          </div>
        </SortableContext>
        {activeId && !activeIsRow && <NewRowZone label={t("panel.keyboard.dropNewRow")} />}
        <DragOverlay>
          {activeId && !activeIsRow ? (
            <div className="flex items-center justify-center rounded-lg border border-primary/50 bg-surface px-3 py-2 text-sm font-medium text-text shadow-lg">
              {buttonLabel(buttonsByKey.get(activeId), activeId)}
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>

      {selected && selectedButton && (
        <div className="mt-3 rounded-lg border border-primary/30 bg-primary/5 p-2.5">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="me-auto truncate text-sm font-semibold text-text">{buttonLabel(selectedButton)}</span>
            <ActionButton label={t("panel.keyboard.rowUp")} onClick={() => move(selected, "up")}>
              <ArrowUp size={14} />
            </ActionButton>
            <ActionButton label={t("panel.keyboard.rowDown")} onClick={() => move(selected, "down")}>
              <ArrowDown size={14} />
            </ActionButton>
            <ActionButton label={t("panel.keyboard.moveRight")} onClick={() => move(selected, "start")}>
              <ArrowRight size={14} />
            </ActionButton>
            <ActionButton label={t("panel.keyboard.moveLeft")} onClick={() => move(selected, "end")}>
              <ArrowLeft size={14} />
            </ActionButton>
            <ActionButton
              label={selectedHidden ? t("panel.keyboard.showToUser") : t("panel.keyboard.hideFromUser")}
              onClick={() => toggleHidden(selected)}
            >
              {selectedHidden ? <Eye size={14} /> : <EyeOff size={14} />}
            </ActionButton>
            <ActionButton label={t("panel.keyboard.editButton")} onClick={() => onEditButton(selected)}>
              <Pencil size={14} />
            </ActionButton>
          </div>
          {selectedButton.blocked && (
            <p className="mt-2 flex items-start gap-1.5 rounded-md bg-warning/10 px-2.5 py-2 text-xs text-warning">
              <AlertTriangle size={13} className="mt-0.5 shrink-0" />
              {blockedLabels(t)[selectedButton.blocked] || selectedButton.blocked}
            </p>
          )}
        </div>
      )}

      <div className="mt-3 space-y-1">
        <Hint>{t("panel.keyboard.layoutHint")}</Hint>
        {data.glass_mode && <Hint>{t("panel.keyboard.glassModeOn")}</Hint>}
      </div>
    </div>
  );

  return (
    <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
      <div className="order-2 lg:order-1">{editor}</div>
      <div className="order-1 lg:sticky lg:top-4 lg:order-2">
        <KeyboardPreview rows={rows} hidden={hidden} buttonsByKey={buttonsByKey} glassMode={data.glass_mode} />
      </div>
    </div>
  );
}

function SortableRow({
  id,
  index,
  empty,
  dropTarget,
  emptyLabel,
  children,
}: {
  id: string;
  index: number;
  empty: boolean;
  dropTarget: boolean;
  emptyLabel: string;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging, isOver } =
    useSortable({ id });
  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Translate.toString(transform), transition }}
      className={`flex items-stretch gap-1.5 rounded-lg border bg-surface-2/60 p-1.5 ${
        isDragging
          ? "z-10 border-primary/50 opacity-80 shadow-lg"
          : dropTarget || isOver
            ? "border-primary/60 bg-primary/10"
            : "border-border"
      }`}
    >
      <button
        type="button"
        ref={setActivatorNodeRef}
        {...attributes}
        {...listeners}
        aria-label={t("panel.keyboard.dragRow")}
        title={t("panel.keyboard.dragRow")}
        className="flex w-7 shrink-0 cursor-grab touch-none flex-col items-center justify-center rounded-md text-muted hover:bg-surface hover:text-text active:cursor-grabbing"
      >
        <GripVertical size={15} />
        <span className="text-[10px] leading-none">{index + 1}</span>
      </button>
      <div className="flex min-h-[40px] min-w-0 flex-1 gap-1.5">
        {children}
        {empty && <p className="flex flex-1 items-center justify-center px-2 text-center text-xs text-muted">{emptyLabel}</p>}
      </div>
    </div>
  );
}

function SortableChip({
  id,
  label,
  hidden,
  blocked,
  selected,
  insertBefore,
  onSelect,
}: {
  id: string;
  label: string;
  hidden: boolean;
  blocked: boolean;
  selected: boolean;
  insertBefore: boolean;
  onSelect: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  return (
    <button
      type="button"
      ref={setNodeRef}
      style={{ transform: CSS.Translate.toString(transform), transition }}
      {...attributes}
      {...listeners}
      onClick={onSelect}
      className={`flex min-w-0 flex-1 select-none items-center justify-center gap-1.5 rounded-md border px-2 py-2 text-xs font-medium transition-colors sm:text-sm ${
        hidden ? "border-dashed border-border bg-transparent text-muted" : "border-border bg-surface text-text"
      } ${selected ? "ring-2 ring-primary/60" : ""} ${
        insertBefore ? "outline-dashed outline-2 outline-offset-2 outline-primary" : ""
      } ${isDragging ? "opacity-30" : "hover:border-primary/40"}`}
    >
      <span className="truncate">{label}</span>
      {blocked && <AlertTriangle size={13} className="shrink-0 text-warning" />}
      {hidden && <EyeOff size={13} className="shrink-0" />}
    </button>
  );
}

function NewRowZone({ label }: { label: string }) {
  const { setNodeRef, isOver } = useDroppable({ id: NEW_ROW_ZONE });
  return (
    <div
      ref={setNodeRef}
      className={`mt-2 flex items-center justify-center gap-1.5 rounded-lg border-2 border-dashed p-3 text-xs transition-colors ${
        isOver ? "border-primary/60 bg-primary/10 text-primary" : "border-border text-muted"
      }`}
    >
      <Plus size={14} />
      {label}
    </div>
  );
}

function ActionButton({ label, onClick, children }: { label: string; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      onClick={onClick}
      className="flex h-8 items-center gap-1 rounded-md border border-border bg-surface px-2 text-xs text-muted transition-colors hover:border-primary/40 hover:text-text"
    >
      {children}
      <span className="hidden xl:inline">{label}</span>
    </button>
  );
}

function KeyboardPreview({
  rows,
  hidden,
  buttonsByKey,
  glassMode,
}: {
  rows: LayoutRow[];
  hidden: string[];
  buttonsByKey: Map<string, PanelKeyboardButton>;
  glassMode: boolean;
}) {
  const { t } = useTranslation();
  const [collapsed, setCollapsed] = useState(false);
  const visible = rows
    .map((row) => row.keys.filter((key) => !hidden.includes(key) && !buttonsByKey.get(key)?.blocked))
    .filter((keys) => keys.length > 0);
  return (
    <div className="rounded-xl border border-border bg-surface p-3">
      <button
        type="button"
        onClick={() => setCollapsed(!collapsed)}
        aria-expanded={!collapsed}
        className="flex w-full items-center gap-1.5 text-xs font-medium text-muted lg:pointer-events-none"
      >
        <Send size={13} className="text-primary" />
        {t("panel.keyboard.preview")}
        <ChevronDown size={14} className={`ms-auto transition-transform lg:hidden ${collapsed ? "" : "rotate-180"}`} />
      </button>
      <div className={`mt-2 ${collapsed ? "hidden lg:block" : ""}`}>
      <div className="rounded-lg bg-surface-2 p-2">
        {visible.length === 0 ? (
          <p className="py-6 text-center text-xs text-muted">{t("panel.keyboard.previewEmpty")}</p>
        ) : (
          <div className="space-y-1.5">
            {visible.map((keys, index) => (
              <div key={index} className="flex gap-1.5">
                {keys.map((key) => {
                  const button = buttonsByKey.get(key);
                  return (
                    <ButtonChip
                      key={key}
                      label={buttonLabel(button, key)}
                      style={renderedStyle(button, glassMode)}
                      className="flex-1"
                    />
                  );
                })}
              </div>
            ))}
          </div>
        )}
      </div>
      <p className="mt-2 text-[11px] leading-relaxed text-muted">{t("panel.keyboard.previewHint")}</p>
      </div>
    </div>
  );
}
