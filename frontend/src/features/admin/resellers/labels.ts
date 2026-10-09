import type { TFunction } from "i18next";

export {
  EVENT_TONE,
  STATUS_TONE,
  eventAmount,
  eventLabels,
  formatRunway,
  runwayTone,
  statusLabels,
} from "../../../lib/resellerLabels";
import { resellerModeLabel } from "../../../lib/resellerLabels";
export type { ResellerTone as Tone } from "../../../lib/resellerLabels";

export const GB = 1024 ** 3;

/** Plan type names; the same wording as the web app and the bot. */
export const pricingLabels = (t: TFunction): Record<string, string> =>
  Object.fromEntries(["fixed", "per_gb", "per_tb", "hourly", "usage"].map((mode) => [mode, resellerModeLabel(t, mode)]));
