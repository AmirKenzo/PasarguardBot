import type {
  LogoutRequest,
  PhoneLoginStartRequest,
  PhoneLoginVerifyRequest,
  WebAppChangeResponse,
  WebAppInfoResponse,
} from "../../types/webapp";
import i18n from "../../i18n";
import { apiGet, apiPost, authHeaders, ApiError } from "./client";

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) || "/api/webapp";

/** GET /webapp/info — Telegram init-data goes in a header, never the query string. */
export async function getInfoWithInitData(rawInitData: string): Promise<WebAppInfoResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/info`, {
      headers: authHeaders({ init_data: rawInitData }),
    });
  } catch {
    throw new ApiError(i18n.t("apiErrors.connectionFailed"));
  }
  const payload = (await res.json()) as WebAppInfoResponse;
  if (!payload.ok) throw new ApiError(payload.error || i18n.t("apiErrors.authError"));
  return payload;
}

export function getInfoSession(sessionToken: string) {
  return apiGet<WebAppInfoResponse>("/info/session", {}, { session_token: sessionToken });
}

export function otpStart(body: PhoneLoginStartRequest) {
  return apiPost<WebAppChangeResponse>("/otp/start", body);
}

export function otpVerify(body: PhoneLoginVerifyRequest) {
  return apiPost<WebAppInfoResponse>("/otp/verify", body);
}

export function logout(body: LogoutRequest) {
  return apiPost<WebAppChangeResponse>("/logout", {}, { session_token: body.session_token });
}
