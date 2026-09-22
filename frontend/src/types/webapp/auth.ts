/** Mirrors app/models/webapp/auth.py */
import type { ServiceStatus, UserProfile } from "./common";

export interface PhoneLoginStartRequest {
  phone: string;
}

export interface PhoneLoginVerifyRequest {
  phone: string;
  code: string;
}

export interface LogoutRequest {
  session_token: string;
}

export interface ApiKeyLoginRequest {
  api_key: string;
}

export interface ApiKeyGenerateRequest {
  session_token?: string | null;
  init_data?: string | null;
}

export interface ApiKeyGenerateResponse {
  ok: boolean;
  api_key?: string | null;
  created_at?: number | null;
  error?: string | null;
}

export type ApiKeyLoginMode = "none" | "phone_verified" | "all";

export interface WebAppInfoResponse {
  ok: boolean;
  user?: UserProfile | null;
  services?: ServiceStatus[] | null;
  error?: string | null;
  session_token?: string | null;
  api_key_login_mode: ApiKeyLoginMode;
}

export interface WebAppChangeResponse {
  ok: boolean;
  subscription_url?: string | null;
  error?: string | null;
}
