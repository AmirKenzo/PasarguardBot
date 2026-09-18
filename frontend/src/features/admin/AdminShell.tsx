import { useEffect, useLayoutEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Activity,
  ArrowLeft,
  ArrowRight,
  BarChart3,
  Boxes,
  CreditCard,
  Gift,
  Keyboard,
  LayoutDashboard,
  Megaphone,
  Menu,
  MessageSquareText,
  Radio,
  Receipt,
  Server,
  Settings,
  Store,
  Tags,
  Users,
  Wrench,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { PageTransition } from "../../components/layout/PageTransition";
import { AppVersion, FullscreenToggle, LanguageToggle, ThemeToggle } from "../../components/ui";
import { panelDashboardApi } from "../../api/panel";
import { usePanelQuery } from "../../queries/usePanelApi";
import { SessionExpiry } from "./components";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
  /** Key in the backend's badge map, when this section has a pending count. */
  badge?: string;
}

interface NavGroup {
  title: string;
  items: NavItem[];
}

const navGroups = (t: TFunction): NavGroup[] => [
  {
    title: t("panel.shell.groupOverview"),
    items: [
      { to: "/panel", label: t("panel.common.dashboard"), icon: LayoutDashboard, end: true },
      { to: "/panel/reports", label: t("panel.common.reports"), icon: BarChart3 },
      { to: "/panel/audit", label: t("panel.common.auditLog"), icon: Activity },
    ],
  },
  {
    title: t("panel.shell.groupSales"),
    items: [
      { to: "/panel/users", label: t("panel.common.users"), icon: Users },
      { to: "/panel/services", label: t("panel.common.services"), icon: Boxes },
      { to: "/panel/transactions", label: t("panel.common.transactions"), icon: Receipt, badge: "transactions" },
      { to: "/panel/plans", label: t("panel.common.salesPlans"), icon: Tags },
      { to: "/panel/discounts", label: t("panel.common.discountCode"), icon: Gift },
    ],
  },
  {
    title: t("panel.shell.groupInfrastructure"),
    items: [
      { to: "/panel/panels", label: t("panel.common.panels"), icon: Server },
      { to: "/panel/resellers", label: t("panel.common.resellers"), icon: Store },
      { to: "/panel/reseller-plans", label: t("panel.common.resellerPlans"), icon: Tags },
      { to: "/panel/payments", label: t("panel.common.paymentGateways"), icon: CreditCard },
    ],
  },
  {
    title: t("panel.shell.groupOutreach"),
    items: [
      { to: "/panel/broadcast", label: t("panel.common.broadcast"), icon: Megaphone },
      { to: "/panel/channels", label: t("panel.common.channels"), icon: Radio },
      { to: "/panel/texts", label: t("panel.common.botTexts"), icon: MessageSquareText },
      { to: "/panel/referral", label: t("panel.common.referral"), icon: Gift },
    ],
  },
  {
    title: t("panel.shell.groupConfiguration"),
    items: [
      { to: "/panel/keyboard", label: t("panel.common.keyboardLayout"), icon: Keyboard },
      { to: "/panel/settings", label: t("panel.common.botSettings"), icon: Settings },
      { to: "/panel/tools", label: t("panel.common.tools"), icon: Wrench },
    ],
  },
];

function BrandMark({ size = "lg" }: { size?: "lg" | "base" }) {
  const { t } = useTranslation();
  return (
    <span
      className={`bg-gradient-to-l from-primary to-accent bg-clip-text font-extrabold tracking-tight text-transparent ${
        size === "lg" ? "text-lg" : "text-base"
      }`}
    >
      {t("panel.shell.title")}
    </span>
  );
}

function NavList({
  badges,
  layoutId,
  onNavigate,
}: {
  badges: Record<string, number>;
  /** Unique per mounted instance — the desktop sidebar and the drawer are both
   *  in the DOM at once, and a shared id makes framer-motion treat the two
   *  active pills as one element. */
  layoutId: string;
  onNavigate?: () => void;
}) {
  const { t } = useTranslation();
  return (
    <nav className="space-y-3">
      {navGroups(t).map((group, index) => (
        <div key={group.title} className={index > 0 ? "border-t border-border/60 pt-3" : ""}>
          <p className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-wide text-muted/70">{group.title}</p>
          <div className="space-y-0.5">
            {group.items.map((item) => {
              const count = item.badge ? badges[item.badge] || 0 : 0;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    `relative flex items-center gap-2.5 rounded-md px-3 py-2 text-[13px] font-medium transition-colors ${
                      isActive ? "text-primary" : "text-muted hover:text-text"
                    }`
                  }
                >
                  {({ isActive }) => (
                    <>
                      {isActive && (
                        <motion.span
                          layoutId={layoutId}
                          className="absolute inset-0 rounded-md bg-primary/10"
                          transition={{ type: "spring", stiffness: 420, damping: 34 }}
                        />
                      )}
                      <span className="relative z-10 flex items-center justify-center">
                        <item.icon size={16} strokeWidth={isActive ? 2.3 : 1.8} />
                      </span>
                      <span className="relative z-10 flex-1 truncate">{item.label}</span>
                      {count > 0 && (
                        <span className="relative z-10 rounded-full bg-warning/15 px-1.5 py-0.5 text-[10px] font-medium text-warning">
                          {count}
                        </span>
                      )}
                    </>
                  )}
                </NavLink>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );
}

function BackToWebApp() {
  const { t, i18n } = useTranslation();
  const BackIcon = i18n.dir() === "rtl" ? ArrowRight : ArrowLeft;
  return (
    <NavLink
      to="/"
      className="flex items-center gap-1.5 rounded-md px-1 py-1 text-xs text-muted transition-colors hover:text-text"
    >
      <BackIcon size={14} />
      {t("panel.shell.backToWebApp")}
    </NavLink>
  );
}

export default function AdminShell() {
  const { t } = useTranslation();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const location = useLocation();

  const { data } = usePanelQuery(["me"], (auth) => panelDashboardApi.getMe(auth), {
    refetchInterval: 60_000,
  });
  const badges = data?.badges || {};

  // React Router's plain <Routes> tree doesn't reset scroll on navigation
  // (that's only built into its data-router APIs), so without this,
  // navigating away from a page scrolled down leaves the new page's content
  // below the fold until the user scrolls back up manually.
  useLayoutEffect(() => {
    window.scrollTo(0, 0);
  }, [location.pathname]);

  useEffect(() => {
    setDrawerOpen(false);
  }, [location.key]);

  return (
    <div className="flex min-h-screen w-full">
      <SessionExpiry />
      <aside className="safe-area-pt sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-l border-border bg-surface p-4 md:flex">
        <div className="mb-5 flex items-center justify-between px-1">
          <BrandMark />
        </div>
        <div className="-mx-1 flex-1 overflow-y-auto px-1">
          <NavList badges={badges} layoutId="admin-sidebar-active" />
        </div>
        <div className="mt-auto flex flex-col gap-3 border-t border-border/60 px-1 pt-3">
          <BackToWebApp />
          <div className="flex items-center justify-center gap-1 rounded-lg bg-surface-2/60 p-1">
            <ThemeToggle />
            <LanguageToggle />
            <FullscreenToggle />
          </div>
          <AppVersion className="text-center" />
        </div>
      </aside>

      <div className="flex min-h-screen w-full flex-1 flex-col">
        <header className="safe-area-pt sticky top-0 z-20 flex items-center justify-between border-b border-border bg-surface/90 px-4 pb-3 pt-4 backdrop-blur md:hidden">
          <button
            onClick={() => setDrawerOpen(true)}
            className="rounded-md p-1.5 text-text transition-colors hover:bg-surface-2"
            aria-label={t("panel.shell.menu")}
          >
            <Menu size={20} />
          </button>
          <BrandMark size="base" />
          <div className="flex items-center gap-2">
            <LanguageToggle />
            <ThemeToggle />
            <FullscreenToggle />
          </div>
        </header>

        <main className="mx-auto w-full max-w-7xl flex-1 space-y-4 px-4 pb-10 pt-4 md:px-6 lg:px-8">
          <PageTransition key={location.pathname}>
            <div className="space-y-4">
              <Outlet />
            </div>
          </PageTransition>
        </main>
      </div>

      {/* The drawer stays mounted and slides with a CSS transition. An
          AnimatePresence block whose children sit inside a fragment is not
          tracked reliably, which left the drawer stuck open after a tap. */}
      <div
        aria-hidden={!drawerOpen}
        onClick={() => setDrawerOpen(false)}
        className={`fixed inset-0 z-40 bg-overlay transition-opacity duration-200 md:hidden ${
          drawerOpen ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      />
      <aside
        onClick={(event) => {
          // Catch the tap on the container, so closing does not depend on
          // NavLink forwarding its own onClick.
          if (event.target instanceof Element && event.target.closest("a")) {
            setDrawerOpen(false);
          }
        }}
        className={`fixed inset-y-0 z-50 flex w-64 flex-col border-border bg-surface p-4 transition-transform duration-200 md:hidden ltr:left-0 ltr:border-r rtl:right-0 rtl:border-l ${
          drawerOpen ? "translate-x-0" : "pointer-events-none ltr:-translate-x-full rtl:translate-x-full"
        }`}
      >
        <div className="mb-5 flex items-center justify-between px-1">
          <BrandMark />
          <button
            onClick={() => setDrawerOpen(false)}
            className="rounded-full p-1.5 text-muted transition-colors hover:bg-surface-2"
            aria-label={t("common.close")}
          >
            <X size={18} />
          </button>
        </div>
        <div className="-mx-1 flex-1 overflow-y-auto px-1">
          <NavList badges={badges} layoutId="admin-drawer-active" onNavigate={() => setDrawerOpen(false)} />
        </div>
        <div className="mt-auto px-1 pt-4">
          <BackToWebApp />
        </div>
      </aside>
    </div>
  );
}
