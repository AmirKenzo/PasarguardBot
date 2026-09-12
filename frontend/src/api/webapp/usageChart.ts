import type { WebAppUsageChartRequest, WebAppUsageChartResponse } from "../../types/webapp";
import { apiPost } from "./client";

export function getUsageChart(body: WebAppUsageChartRequest) {
  return apiPost<WebAppUsageChartResponse>("/services/usage-chart", body);
}
