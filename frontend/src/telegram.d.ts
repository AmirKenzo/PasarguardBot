interface TelegramThemeParams {
  bg_color?: string;
  text_color?: string;
  hint_color?: string;
  link_color?: string;
  button_color?: string;
  button_text_color?: string;
  secondary_bg_color?: string;
  header_bg_color?: string;
  accent_text_color?: string;
  section_bg_color?: string;
  section_header_text_color?: string;
  subtitle_text_color?: string;
  destructive_text_color?: string;
}

interface TelegramWebAppUser {
  id: number;
  first_name?: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
  language_code?: string;
}

interface TelegramBackButton {
  isVisible: boolean;
  show: () => void;
  hide: () => void;
  onClick: (cb: () => void) => void;
  offClick: (cb: () => void) => void;
}

interface TelegramMainButton {
  text: string;
  color: string;
  textColor: string;
  isVisible: boolean;
  isActive: boolean;
  isProgressVisible: boolean;
  setText: (text: string) => void;
  show: () => void;
  hide: () => void;
  enable: () => void;
  disable: () => void;
  showProgress: (leaveActive?: boolean) => void;
  hideProgress: () => void;
  onClick: (cb: () => void) => void;
  offClick: (cb: () => void) => void;
}

interface TelegramHapticFeedback {
  impactOccurred: (style: "light" | "medium" | "heavy" | "rigid" | "soft") => void;
  notificationOccurred: (type: "error" | "success" | "warning") => void;
  selectionChanged: () => void;
}

type TelegramEventType =
  | "themeChanged"
  | "viewportChanged"
  | "fullscreenChanged"
  | "fullscreenFailed"
  | "safeAreaChanged"
  | "contentSafeAreaChanged"
  | "mainButtonClicked"
  | "backButtonClicked"
  | "settingsButtonClicked"
  | "invoiceClosed"
  | "popupClosed";

interface TelegramSafeAreaInset {
  top: number;
  bottom: number;
  left: number;
  right: number;
}

interface TelegramWebApp {
  initData: string;
  initDataUnsafe: { user?: TelegramWebAppUser; start_param?: string };
  version: string;
  platform: string;
  colorScheme: "light" | "dark";
  themeParams: TelegramThemeParams;
  isExpanded: boolean;
  isFullscreen?: boolean;
  viewportHeight: number;
  viewportStableHeight: number;
  /** Device-level inset (notch, OS status bar). */
  safeAreaInset?: TelegramSafeAreaInset;
  /** Additional inset from Telegram's own floating UI (close/minimize
   * controls in Fullscreen mode) drawn on top of the page content. */
  contentSafeAreaInset?: TelegramSafeAreaInset;
  headerColor?: string;
  backgroundColor?: string;
  BackButton: TelegramBackButton;
  MainButton: TelegramMainButton;
  HapticFeedback: TelegramHapticFeedback;
  close: () => void;
  expand: () => void;
  ready: () => void;
  requestFullscreen?: () => void;
  exitFullscreen?: () => void;
  onEvent: (event: TelegramEventType, cb: () => void) => void;
  offEvent: (event: TelegramEventType, cb: () => void) => void;
  setHeaderColor: (color: string) => void;
  setBackgroundColor: (color: string) => void;
  openLink: (url: string, options?: { try_instant_view?: boolean }) => void;
  openTelegramLink: (url: string) => void;
  openInvoice: (url: string, callback?: (status: "paid" | "cancelled" | "failed" | "pending") => void) => void;
  showAlert: (message: string, cb?: () => void) => void;
  showConfirm: (message: string, cb?: (confirmed: boolean) => void) => void;
  /** Native "share phone number" prompt. `sent` is true only if the user approved sharing. */
  requestContact?: (cb?: (sent: boolean) => void) => void;
}

declare global {
  interface Window {
    Telegram?: { WebApp: TelegramWebApp };
  }
}

export {};
