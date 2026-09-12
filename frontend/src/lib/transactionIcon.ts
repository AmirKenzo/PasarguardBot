import { CreditCard, Wallet, type LucideIcon } from "lucide-react";

const EMOJI_ICONS: Record<string, LucideIcon> = {
  "💳": CreditCard,
  "💰": Wallet,
};

/** Backend sends a raw emoji per transaction source (card/crypto); map it to a matching Lucide icon. */
export function transactionIcon(emoji: string): LucideIcon {
  return EMOJI_ICONS[emoji] ?? Wallet;
}
