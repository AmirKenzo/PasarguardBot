import type {
  LogoutRequest,
  PhoneLoginStartRequest,
  PhoneLoginVerifyRequest,
  WebAccountChangePasswordRequest,
  WebAccountChangePasswordResponse,
  WebAccountCreateRequest,
  WebAccountCreateResponse,
  WebAppChangeResponse,
  WebAppInfoResponse,
  WebAppLoginRequest,
  WebRegistrationModeResponse,
} from "../../types/webapp";
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
    throw new ApiError("ارتباط با سرور برقرار نشد");
  }
  const payload = (await res.json()) as WebAppInfoResponse;
  if (!payload.ok) throw new ApiError(payload.error || "خطای احراز هویت");
  return payload;
}

export function getInfoSession(sessionToken: string) {
  return apiGet<WebAppInfoResponse>("/info/session", {}, { session_token: sessionToken });
}

export function login(body: WebAppLoginRequest) {
  return apiPost<WebAppInfoResponse>("/login", body);
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

export function createAccount(body: WebAccountCreateRequest) {
  const { session_token, ...rest } = body;
  return apiPost<WebAccountCreateResponse>("/account/create", rest, { session_token });
}

export function changePassword(body: WebAccountChangePasswordRequest) {
  const { session_token, ...rest } = body;
  return apiPost<WebAccountChangePasswordResponse>("/account/change-password", rest, { session_token });
}

export function getRegistrationStatus() {
  return apiGet<WebRegistrationModeResponse>("/registration/status");
}
