import type { ReactNode } from "react";
import { EmptyState, Skeleton } from "../../../components/ui";
import { useTranslation } from "react-i18next";

export interface Column<Row> {
  key: string;
  header: string;
  /** Renders the cell; falls back to the raw value when omitted. */
  cell: (row: Row) => ReactNode;
  /** Hidden below the `sm` breakpoint — use for secondary detail. */
  secondary?: boolean;
}

export interface DataTableProps<Row> {
  columns: Column<Row>[];
  rows: Row[];
  rowKey: (row: Row) => string | number;
  loading?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
}

export function DataTable<Row>({
  columns,
  rows,
  rowKey,
  loading = false,
  emptyTitle,
  emptyDescription,
}: DataTableProps<Row>) {
  const { t } = useTranslation();
  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, index) => (
          <Skeleton key={index} className="h-12 w-full rounded-md" />
        ))}
      </div>
    );
  }

  if (!rows.length) {
    return <EmptyState title={emptyTitle ?? t("panel.dataTable.empty")} description={emptyDescription} />;
  }

  return (
    <div className="-mx-4 overflow-x-auto px-4">
      <table className="w-full min-w-[36rem] border-collapse text-sm">
        <thead>
          <tr className="border-b border-border text-right text-xs text-muted">
            {columns.map((column) => (
              <th
                key={column.key}
                className={`whitespace-nowrap px-3 py-2 font-medium ${column.secondary ? "hidden sm:table-cell" : ""}`}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)} className="border-b border-border/60 last:border-0 hover:bg-surface-2/60">
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={`px-3 py-2.5 align-middle text-text ${column.secondary ? "hidden sm:table-cell" : ""}`}
                >
                  {column.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
