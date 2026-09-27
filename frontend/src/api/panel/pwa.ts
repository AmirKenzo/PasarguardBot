import type { ActionResponse, PanelAuthRequest, PwaIconUploadResponse, PwaSettingsResponse, PwaSettingsSaveRequest } from "../../types/panel";
import { authHeaders } from "../webapp/client";
import { ApiError, panelPost } from "./client";

const API_BASE = (import.meta.env.VITE_PANEL_API_BASE as string | undefined) || "/api/panel";

export function getPwaSettings(body: PanelAuthRequest) {
  return panelPost<PwaSettingsResponse>("/pwa", body);
}

export function savePwaSettings(body: PwaSettingsSaveRequest) {
  return panelPost<ActionResponse>("/pwa/save", body);
}

/** Multipart upload — the only panel call that isn't a JSON body. */
export async function uploadPwaIcon(file: File, auth: PanelAuthRequest): Promise<PwaIconUploadResponse> {
  const form = new FormData();
  form.append("file", file);
  if (auth.session_token) form.append("session_token", auth.session_token);
  if (auth.init_data) form.append("init_data", auth.init_data);

  let res: Response;
  try {
    res = await fetch(`${API_BASE}/pwa/icon`, {
      method: "POST",
      headers: authHeaders(auth),
      body: form,
    });
  } catch {
    throw new ApiError("ارتباط با سرور برقرار نشد");
  }
  const payload = (await res.json().catch(() => ({}))) as PwaIconUploadResponse;
  if (!payload.ok) throw new ApiError(payload.error || "خطای ناشناخته");
  return payload;
}
