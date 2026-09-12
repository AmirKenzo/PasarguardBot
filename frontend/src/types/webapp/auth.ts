/** Mirrors app/models/webapp/auth.py */
import type { ServiceStatus, UserProfile } from "./common";

export interface WebAppLoginRequest {
  username: string;
  password: string;
}

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

export interface WebAppInfoResponse {
  ok: boolean;
  user?: UserProfile | null;
  services?: ServiceStatus[] | null;
  error?: string | null;
  session_token?: string | null;
}

export interface WebAppChangeResponse {
  ok: boolean;
  subscription_url?: string | null;
  error?: string | null;
}

export interface WebAccountCreateRequest {
  username: string;
  password: string;
  session_token?: string | null;
}

export interface WebAccountCreateResponse {
  ok: boolean;
  message: string;
  error?: string | null;
}

export interface WebAccountChangePasswordRequest {
  new_password: string;
  session_token?: string | null;
}

export interface WebAccountChangePasswordResponse {
  ok: boolean;
  message: string;
  error?: string | null;
}

export interface WebRegistrationModeResponse {
  ok: boolean;
  message: string;
  error?: string | null;
}
