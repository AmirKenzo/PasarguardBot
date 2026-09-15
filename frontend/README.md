# PasarguardBot WebApp Frontend

**Run Bun from this folder (`frontend/`).** Use `cd frontend` then `bun install` / `bun run build`.

## Development

```bash
cd frontend
bun install
bun run dev
```

Open `http://localhost:5174` and use hash routing (e.g. `#/login`). API calls are proxied to the FastAPI backend at `http://127.0.0.1:8001` from `vite.config.ts`.

If the bot/backend is not running locally and you want to preview against a real API, create `frontend/.env.local`:

```bash
VITE_API_BASE=/api/webapp
VITE_API_PROXY_TARGET=https://your-bot-domain.example
```

Then run:

```bash
bun run dev
```

Open `http://localhost:5174/webapp/#/login` or `http://localhost:5174/webapp/#/services`.

For live preview on a server without rebuilding production assets each time:

```bash
cd frontend
bun run dev --host 0.0.0.0
```

Then open `http://SERVER_IP:5174`. Every frontend change updates through Vite HMR.

## Production Build

```bash
cd frontend
bun install
bun run build
```

Output goes to `frontend/dist/`. The FastAPI backend serves `index.html` at `/api/webapp` and assets at `/webapp/assets`.

Building the Docker image (see the repo `Dockerfile`) runs this automatically in a `frontend-build` stage, so `frontend/dist/` never needs to be committed to git.

## Run Full Stack

1. Start the FastAPI backend (e.g. `python main.py`, with `FASTAPI_PORT` set in `.env`)
2. Build the frontend: `cd frontend && bun install && bun run build`
3. Visit `http://localhost:<FASTAPI_PORT>/api/webapp`
