import { ApiError, authHeaders } from "../webapp/client";
import type { AuthPayload } from "../webapp/client";

const API_BASE = (import.meta.env.VITE_PANEL_API_BASE as string | undefined) || "/api/panel";

export { ApiError };
export type { AuthPayload };

async function parseJson(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    throw new ApiError("پاسخ سرور نامعتبر بود");
  }
}

function stripAuthFields(body: Record<string, unknown>): Record<string, unknown> {
  const next = { ...body };
  delete next.session_token;
  delete next.init_data;
  return next;
}

function authFromBody(body: Record<string, unknown>): AuthPayload {
  return {
    session_token: typeof body.session_token === "string" ? body.session_token : null,
    init_data: typeof body.init_data === "string" ? body.init_data : null,
  };
}

/**
 * Every admin panel endpoint is a POST that answers with `{ ok, error }`.
 * Credentials travel in headers so they never land in URLs or access logs.
 */
export async function panelPost<TRes extends { ok: boolean; error?: string | null }>(
  path: string,
  body: object = {},
  auth?: AuthPayload | null
): Promise<TRes> {
  const raw = body as Record<string, unknown>;
  const resolvedAuth = auth ?? authFromBody(raw);
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(resolvedAuth),
      },
      body: JSON.stringify(stripAuthFields(raw)),
    });
  } catch {
    throw new ApiError("ارتباط با سرور برقرار نشد");
  }
  const payload = (await parseJson(res)) as TRes;
  if (!payload.ok) throw new ApiError(payload.error || "خطای ناشناخته");
  return payload;
}
