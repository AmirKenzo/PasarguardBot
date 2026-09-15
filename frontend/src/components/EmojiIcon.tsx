import {
  AlarmClock,
  BadgeHelp,
  BarChart3,
  CalendarDays,
  CheckCircle2,
  ClipboardList,
  CreditCard,
  Dice5,
  DoorOpen,
  Download,
  Gem,
  Globe2,
  Hash,
  Home,
  LockKeyhole,
  Network,
  Phone,
  QrCode,
  RefreshCw,
  Rocket,
  Satellite,
  Send,
  Settings2,
  ShieldCheck,
  ShoppingCart,
  Signal,
  Sparkles,
  TicketPercent,
  User,
  Users,
  Wallet,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

const ICONS: Record<string, LucideIcon> = {
  credit_card: CreditCard,
  dollar: Wallet,
  money_with_wings: Wallet,
  white_check_mark: CheckCircle2,
  star2: Sparkles,
  sparkles: Sparkles,
  pound: CreditCard,
  house: Home,
  signal_strength: Signal,
  shopping_cart: ShoppingCart,
  bust_in_silhouette: User,
  busts_in_silhouette: Users,
  grey_question: BadgeHelp,
  door: DoorOpen,
  clipboard: ClipboardList,
  qrcode: QrCode,
  refresh: RefreshCw,
  link: Network,
  download: Download,
  send: Send,
  users: Users,
  control_knobs: Settings2,
  lock: LockKeyhole,
  globe: Globe2,
  hash: Hash,
  large_blue_diamond: Gem,
  inbox_tray: Download,
  game_die: Dice5,
  ballot_box: ShieldCheck,
  shield: ShieldCheck,
  calendar: CalendarDays,
  rocket: Rocket,
  globe_with_meridians: Network,
  alarm_clock: AlarmClock,
  satellite: Satellite,
  telephone: Phone,
  ticket: TicketPercent,
  bar_chart: BarChart3,
};

export interface EmojiIconProps {
  /** Icon id used by the existing UI. Renders a Lucide icon when available. */
  id: string;
  size?: number;
  className?: string;
}

export function EmojiIcon({ id, size = 24, className = "" }: EmojiIconProps) {
  const Icon = ICONS[id];
  if (Icon) {
    return (
      <Icon
        size={size}
        strokeWidth={1.9}
        className={`inline-flex shrink-0 text-current ${className}`}
        aria-label={id}
      />
    );
  }

  return (
    <span
      className={`inline-flex items-center justify-center ${className}`}
      style={{ fontSize: size, lineHeight: 1 }}
      aria-label={id}
    >
      {id}
    </span>
  );
}
