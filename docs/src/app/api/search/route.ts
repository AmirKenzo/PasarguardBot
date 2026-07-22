import { source } from '@/lib/source';
import { createFromSource } from 'fumadocs-core/search/server';

export const revalidate = false;

// Arabic tokenizer works for Persian and still matches Latin terms.
export const { staticGET: GET } = createFromSource(source, {
  language: 'arabic',
});
