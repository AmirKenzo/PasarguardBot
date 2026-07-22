import { readFileSync } from 'node:fs';
import { join } from 'node:path';

/** Read version from repo-root pyproject.toml at build time (server-only). */
export function getBotVersion(): string {
  try {
    const raw = readFileSync(join(process.cwd(), '..', 'pyproject.toml'), 'utf8');
    const match = raw.match(/^version\s*=\s*"([^"]+)"/m);
    return match?.[1] ?? '0.0.0';
  } catch {
    return '0.0.0';
  }
}

export const botVersion = getBotVersion();
