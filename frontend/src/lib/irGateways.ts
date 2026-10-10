import { Banknote, Landmark, type LucideIcon } from "lucide-react";
import i18n from "../i18n";

/** Iranian direct gateways known to the UI (titles come from the backend; this only adds an icon). */
export const IR_GATEWAYS: { key: string; icon: LucideIcon }[] = [
  { key: "zarinpal", icon: Landmark },
  { key: "zibal", icon: Banknote },
];

export function irGatewayIcon(key: string): LucideIcon {
  return IR_GATEWAYS.find((gateway) => gateway.key === key)?.icon ?? Landmark;
}

export function irGatewayName(key: string): string {
  return i18n.t(`irGateways.names.${key}`, key);
}

export function isIrGateway(key: string): boolean {
  return IR_GATEWAYS.some((gateway) => gateway.key === key);
}
