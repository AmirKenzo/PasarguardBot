import type {
  BotResellerCreateRequest,
  BotResellerEditRequest,
  BotResellerOk,
  BotResellerStateResponse,
  BotResellerToggleRequest,
  BotResellerUsageResponse,
  BotResellerUserRequest,
  BotResellerUserResponse,
  BotResellerUsersRequest,
  BotResellerUsersResponse,
  WebAppAuthRequest,
} from "../../types/webapp";
import { apiPost } from "./client";

export function getState(body: WebAppAuthRequest) {
  return apiPost<BotResellerStateResponse>("/bot-reseller/state", body);
}

export function listUsers(body: BotResellerUsersRequest) {
  return apiPost<BotResellerUsersResponse>("/bot-reseller/users", body);
}

export function getUser(body: BotResellerUserRequest) {
  return apiPost<BotResellerUserResponse>("/bot-reseller/user", body);
}

export function createUser(body: BotResellerCreateRequest) {
  return apiPost<BotResellerUserResponse>("/bot-reseller/user/create", body);
}

export function editUser(body: BotResellerEditRequest) {
  return apiPost<BotResellerOk>("/bot-reseller/user/edit", body);
}

export function toggleUser(body: BotResellerToggleRequest) {
  return apiPost<BotResellerOk>("/bot-reseller/user/toggle", body);
}

export function revokeLink(body: BotResellerUserRequest) {
  return apiPost<BotResellerUserResponse>("/bot-reseller/user/revoke", body);
}

export function resetUsage(body: BotResellerUserRequest) {
  return apiPost<BotResellerOk>("/bot-reseller/user/reset", body);
}

export function deleteUser(body: BotResellerUserRequest) {
  return apiPost<BotResellerOk>("/bot-reseller/user/delete", body);
}

export function getUsage(body: WebAppAuthRequest) {
  return apiPost<BotResellerUsageResponse>("/bot-reseller/usage", body);
}
