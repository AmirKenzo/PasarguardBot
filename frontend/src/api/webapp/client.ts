import i18n from "../../i18n";

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) || "/api/webapp";

export interface AuthPayload {
  session_token?: string | null;
  init_data?: string | null;
}

export class ApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiError";
  }
}

/** Set by AuthContext so a sliding-session renewal (X-Session-Token response header) can update stored state. */
let onTokenRenewed: ((token: string) => void) | null = null;

export function setTokenRenewedHandler(handler: ((token: string) => void) | null): void {
  onTokenRenewed = handler;
}

function handleTokenRenewal(res: Response): void {
  const renewed = res.headers.get("x-session-token");
  if (renewed) onTokenRenewed?.(renewed);
}

async function parseJson(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    throw new ApiError(i18n.t("apiErrors.invalidResponse"));
  }
}

/** Every response envelope from the backend carries `ok` + optional `error`. */
function unwrap<T extends { ok: boolean; error?: string | null }>(payload: T): T {
  if (!payload.ok) {
    throw new ApiError(payload.error || i18n.t("apiErrors.unknownError"));
  }
  return payload;
}

/** Put credentials in headers so they never land in URLs/query logs. */
export function authHeaders(auth?: AuthPayload | null): Record<string, string> {
  const headers: Record<string, string> = {};
  if (auth?.session_token) {
    headers.Authorization = `Bearer ${auth.session_token}`;
    headers["X-Session-Token"] = auth.session_token;
  }
  if (auth?.init_data) {
    headers["X-Telegram-Init-Data"] = auth.init_data;
  }
  return headers;
}

function stripAuthFields<T extends Record<string, unknown>>(body: T): Record<string, unknown> {
  const next: Record<string, unknown> = { ...body };
  delete next.session_token;
  delete next.init_data;
  return next;
}

function extractAuthFromBody(body: Record<string, unknown>): AuthPayload {
  return {
    session_token: typeof body.session_token === "string" ? body.session_token : null,
    init_data: typeof body.init_data === "string" ? body.init_data : null,
  };
}

export async function apiPost<TRes extends { ok: boolean; error?: string | null }>(
  path: string,
  body: object = {},
  auth?: AuthPayload | null
): Promise<TRes> {
  const raw = body as Record<string, unknown>;
  const resolvedAuth = auth ?? extractAuthFromBody(raw);
  const safeBody = stripAuthFields(raw);
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(resolvedAuth),
      },
      body: JSON.stringify(safeBody),
    });
  } catch {
    throw new ApiError(i18n.t("apiErrors.connectionFailed"));
  }
  handleTokenRenewal(res);
  const payload = (await parseJson(res)) as TRes;
  return unwrap(payload);
}

export async function apiGet<TRes extends { ok: boolean; error?: string | null }>(
  path: string,
  params: Record<string, string | number | undefined | null> = {},
  auth?: AuthPayload | null
): Promise<TRes> {
  const query = new URLSearchParams();
  let resolvedAuth = auth ?? null;
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    if (key === "session_token" || key === "init_data") {
      resolvedAuth = {
        session_token: key === "session_token" ? String(value) : resolvedAuth?.session_token,
        init_data: key === "init_data" ? String(value) : resolvedAuth?.init_data,
      };
      continue;
    }
    query.set(key, String(value));
  }
  const qs = query.toString();
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}${qs ? `?${qs}` : ""}`, {
      headers: { ...authHeaders(resolvedAuth) },
    });
  } catch {
    throw new ApiError(i18n.t("apiErrors.connectionFailed"));
  }
  handleTokenRenewal(res);
  const payload = (await parseJson(res)) as TRes;
  return unwrap(payload);
}

export async function apiPostForm<TRes extends { ok: boolean; error?: string | null }>(
  path: string,
  formData: FormData,
  auth?: AuthPayload | null
): Promise<TRes> {
  // Never keep secrets in multipart fields when headers are available.
  const fromForm: AuthPayload = {
    session_token: (formData.get("session_token") as string | null) || null,
    init_data: (formData.get("init_data") as string | null) || null,
  };
  formData.delete("session_token");
  formData.delete("init_data");
  const resolvedAuth = auth ?? fromForm;

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { ...authHeaders(resolvedAuth) },
      body: formData,
    });
  } catch {
    throw new ApiError(i18n.t("apiErrors.connectionFailed"));
  }
  handleTokenRenewal(res);
  const payload = (await parseJson(res)) as TRes;
  return unwrap(payload);
}
