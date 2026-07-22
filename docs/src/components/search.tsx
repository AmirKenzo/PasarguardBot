'use client';

import {
  SearchDialog,
  SearchDialogClose,
  SearchDialogContent,
  SearchDialogHeader,
  SearchDialogIcon,
  SearchDialogInput,
  SearchDialogList,
  SearchDialogOverlay,
  type SharedProps,
} from 'fumadocs-ui/components/dialog/search';
import { useDocsSearch } from 'fumadocs-core/search/client';
import { createContentHighlighter, type SortedResult } from 'fumadocs-core/search';
import { create, getByID, load, search as oramaSearch } from '@orama/orama';
import { useState } from 'react';

// Orama's generic DB typing explodes in TS; keep runtime-safe with a loose handle.
type LooseDb = object;

let dbPromise: Promise<LooseDb> | null = null;

function indexUrl(): string {
  const base = (process.env.NEXT_PUBLIC_BASE_PATH || '').replace(/\/$/, '');
  return `${base}/api/search`;
}

async function loadDb(): Promise<LooseDb> {
  if (!dbPromise) {
    dbPromise = (async () => {
      const res = await fetch(indexUrl());
      if (!res.ok) {
        throw new Error(`Search index HTTP ${res.status}`);
      }
      const data = (await res.json()) as Record<string, unknown>;
      // Fumadocs wraps Orama dump with `{ type, ...dump }`. Loading `type` breaks groupBy.
      const { type: _type, ...dump } = data;
      const db = create({
        schema: { _: 'string' },
        language: 'arabic',
      });
      load(db, dump as never);
      return db as LooseDb;
    })().catch((err: unknown) => {
      dbPromise = null;
      throw err;
    });
  }
  return dbPromise;
}

async function runSearch(query: string): Promise<SortedResult[]> {
  const q = query.trim();
  if (!q) return [];

  try {
    const db = await loadDb();
    const highlighter = createContentHighlighter(q);
    const result = await (oramaSearch as (db: LooseDb, params: object) => Promise<{
      groups?: Array<{
        values: unknown[];
        result: Array<{
          id: string | number;
          document: {
            id?: string | number;
            type?: string;
            content?: string;
            breadcrumbs?: string[];
            url?: string;
          };
        }>;
      }>;
    }>)(db, {
      term: q,
      limit: 60,
      mode: 'fulltext',
      properties: ['content'],
      groupBy: {
        properties: ['page_id'],
        maxResult: 8,
      },
    });

    const list: SortedResult[] = [];
    for (const item of result.groups ?? []) {
      const pageId = String(item.values[0]);
      const page = (getByID as (db: LooseDb, id: string) => {
        content?: string;
        breadcrumbs?: string[];
        url?: string;
      } | null)(db, pageId);
      if (page) {
        list.push({
          id: pageId,
          type: 'page',
          content: highlighter.highlightMarkdown(String(page.content ?? '')),
          breadcrumbs: page.breadcrumbs,
          url: String(page.url),
        });
      }
      for (const hit of item.result) {
        if (hit.document.type === 'page') continue;
        const hitType = String(hit.document.type ?? 'text');
        list.push({
          id: String(hit.document.id ?? hit.id),
          content: highlighter.highlightMarkdown(String(hit.document.content ?? '')),
          breadcrumbs: hit.document.breadcrumbs as string[] | undefined,
          type: hitType === 'heading' ? 'heading' : 'text',
          url: String(hit.document.url),
        });
      }
    }
    return list.slice(0, 60);
  } catch (err) {
    console.error('[docs search]', err);
    return [];
  }
}

export default function DefaultSearchDialog(props: SharedProps) {
  const [client] = useState(() => ({
    deps: [] as unknown[],
    search: runSearch,
  }));

  const { search: searchValue, setSearch, query } = useDocsSearch({ client });

  return (
    <SearchDialog
      search={searchValue}
      onSearchChange={setSearch}
      isLoading={query.isLoading}
      {...props}
    >
      <SearchDialogOverlay />
      <SearchDialogContent>
        <SearchDialogHeader>
          <SearchDialogIcon />
          <SearchDialogInput placeholder="جستجو در مستندات…" />
          <SearchDialogClose />
        </SearchDialogHeader>
        <SearchDialogList items={query.data !== 'empty' ? query.data : null} />
      </SearchDialogContent>
    </SearchDialog>
  );
}
