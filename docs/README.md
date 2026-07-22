# PasarguardBot Docs (Fumadocs + Bun)

```bash
cd docs
bun install
bun run dev
```

Open http://localhost:3000

Content lives in `content/docs/` (MDX). Version badge is read from repo-root `pyproject.toml`.

```bash
bun run build                      # local static export → out/
GITHUB_PAGES=true bun run build    # same as CI (basePath /PasarguardBot)
bun run start                      # preview out/
```
