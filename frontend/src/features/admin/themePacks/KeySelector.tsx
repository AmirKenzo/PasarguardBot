import { useMemo, useState } from "react";
import { Search, TriangleAlert } from "lucide-react";
import { useTranslation } from "react-i18next";
import { ChipTabs } from "../../../components/ui";
import type { ThemePackButtonInfo, ThemePackOverviewResponse, ThemePackTextInfo } from "../../../types/panel";
import { sectionLabels } from "../keyboard/shared";
import { hintLabel } from "./shared";
import { ToggleRow } from "./ToggleRow";

type Tab = "texts" | "buttons";

interface Group<T> {
  key: string;
  label: string;
  entries: T[];
}

export interface KeySelectorProps {
  overview: ThemePackOverviewResponse;
  textKeys: Set<string>;
  buttonKeys: Set<string>;
  onTextKeys: (next: Set<string>) => void;
  onButtonKeys: (next: Set<string>) => void;
  /** Keys already in the pack being edited; shown as selected and locked. */
  lockedTexts?: Set<string>;
  lockedButtons?: Set<string>;
}

function toggle(set: Set<string>, keys: string[], on: boolean): Set<string> {
  const next = new Set(set);
  for (const key of keys) {
    if (on) next.add(key);
    else next.delete(key);
  }
  return next;
}

export function KeySelector({
  overview,
  textKeys,
  buttonKeys,
  onTextKeys,
  onButtonKeys,
  lockedTexts,
  lockedButtons,
}: KeySelectorProps) {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>("texts");
  const [onlyCustomized, setOnlyCustomized] = useState(true);
  const [search, setSearch] = useState("");
  const needle = search.trim().toLowerCase();
  const buttonSectionNames = sectionLabels(t);

  const textGroups = useMemo<Group<ThemePackTextInfo>[]>(() => {
    const matches = (entry: ThemePackTextInfo) =>
      (!onlyCustomized || entry.langs.length > 0) &&
      (!needle || entry.key.toLowerCase().includes(needle) || entry.title.toLowerCase().includes(needle));
    return overview.text_sections
      .map((section) => ({
        key: section.key,
        label: section.name ? `${section.icon} ${section.name}`.trim() : t("panel.themePacks.otherSection"),
        entries: overview.texts.filter((entry) => entry.section === section.key && matches(entry)),
      }))
      .filter((group) => group.entries.length > 0);
  }, [overview, onlyCustomized, needle, t]);

  const buttonGroups = useMemo<Group<ThemePackButtonInfo>[]>(() => {
    const matches = (entry: ThemePackButtonInfo) =>
      (!onlyCustomized || entry.customized) &&
      (!needle || entry.key.toLowerCase().includes(needle) || entry.title.toLowerCase().includes(needle));
    return overview.button_sections
      .map((section) => ({
        key: section,
        label: buttonSectionNames[section] ?? section,
        entries: overview.buttons.filter((entry) => entry.section === section && matches(entry)),
      }))
      .filter((group) => group.entries.length > 0);
  }, [overview, onlyCustomized, needle, buttonSectionNames]);

  const renderGroups = <T extends ThemePackTextInfo | ThemePackButtonInfo>(
    groups: Group<T>[],
    selected: Set<string>,
    locked: Set<string> | undefined,
    onChange: (next: Set<string>) => void,
    detail: (entry: T) => string
  ) =>
    groups.length === 0 ? (
      <p className="rounded-xl border border-dashed border-border px-3 py-6 text-center text-sm text-muted">
        {onlyCustomized ? t("panel.themePacks.nothingCustomized") : t("panel.themePacks.noMatches")}
      </p>
    ) : (
      groups.map((group) => {
        const keys = group.entries.map((entry) => entry.key).filter((key) => !locked?.has(key));
        const allOn = keys.length > 0 && keys.every((key) => selected.has(key));
        return (
          <div key={group.key} className="rounded-xl border border-border">
            <label className="flex cursor-pointer items-center gap-2.5 border-b border-border bg-surface-2/60 px-3 py-2 text-sm font-semibold text-text">
              <input
                type="checkbox"
                className="h-4 w-4 accent-primary"
                checked={allOn}
                disabled={keys.length === 0}
                onChange={(event) => onChange(toggle(selected, keys, event.target.checked))}
              />
              <span className="flex-1">{group.label}</span>
              <span className="text-xs font-normal text-muted">{group.entries.length}</span>
            </label>
            <ul className="divide-y divide-border">
              {group.entries.map((entry) => {
                const isLocked = locked?.has(entry.key) ?? false;
                return (
                  <li key={entry.key}>
                    <label className="flex cursor-pointer items-start gap-2.5 px-3 py-2">
                      <input
                        type="checkbox"
                        className="mt-1 h-4 w-4 accent-primary"
                        checked={isLocked || selected.has(entry.key)}
                        disabled={isLocked}
                        onChange={(event) => onChange(toggle(selected, [entry.key], event.target.checked))}
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm text-text">{entry.title}</span>
                        <span className="block truncate text-xs text-muted">{detail(entry)}</span>
                        {entry.hints.length > 0 && (
                          <span className="mt-1 flex flex-wrap gap-1">
                            {entry.hints.map((hint) => (
                              <span
                                key={hint}
                                className="inline-flex items-center gap-1 rounded-md bg-warning/12 px-1.5 py-0.5 text-[11px] text-warning"
                              >
                                <TriangleAlert size={11} />
                                {hintLabel(t, hint)}
                              </span>
                            ))}
                          </span>
                        )}
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })
    );

  return (
    <div className="flex flex-col gap-3">
      <ChipTabs
        options={[
          { value: "texts" as Tab, label: t("panel.themePacks.texts"), count: textKeys.size },
          { value: "buttons" as Tab, label: t("panel.themePacks.buttons"), count: buttonKeys.size },
        ]}
        value={tab}
        onChange={setTab}
      />
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex min-w-0 flex-1 items-center gap-2 rounded-xl border border-border bg-surface-2 px-3">
          <Search size={15} className="shrink-0 text-muted" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={t("panel.themePacks.search")}
            className="h-9 min-w-0 flex-1 bg-transparent text-sm text-text outline-none"
          />
        </label>
        <ToggleRow checked={onlyCustomized} onChange={setOnlyCustomized} label={t("panel.themePacks.onlyCustomized")} />
      </div>
      <div className="flex flex-col gap-2.5">
        {tab === "texts"
          ? renderGroups(textGroups, textKeys, lockedTexts, onTextKeys, (entry) =>
              entry.langs.length > 0
                ? t("panel.themePacks.customizedIn", { langs: entry.langs.join(", ").toUpperCase() })
                : t("panel.themePacks.usesDefault")
            )
          : renderGroups(buttonGroups, buttonKeys, lockedButtons, onButtonKeys, (entry) =>
              entry.customized ? t("panel.themePacks.customized") : t("panel.themePacks.usesDefault")
            )}
      </div>
    </div>
  );
}
