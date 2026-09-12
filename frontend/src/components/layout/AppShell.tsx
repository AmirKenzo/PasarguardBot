import { AnimatePresence, motion } from "framer-motion";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Home, ListVideo, ShoppingBag, User, Wallet } from "lucide-react";
import { PageTransition } from "./PageTransition";
import { ThemeToggle } from "../ui/ThemeToggle";
import { AppVersion } from "../ui/AppVersion";

const NAV_ITEMS = [
  { to: "/", label: "خانه", icon: Home, end: true },
  { to: "/services", label: "سرویس‌ها", icon: ListVideo, end: false },
  { to: "/buy", label: "خرید", icon: ShoppingBag, end: false },
  { to: "/balance", label: "کیف پول", icon: Wallet, end: false },
  { to: "/profile", label: "پروفایل", icon: User, end: false },
];

function NavButtons({ orientation }: { orientation: "row" | "col" }) {
  return (
    <>
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) =>
            `relative flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors ${
              orientation === "col" ? "flex-row" : "flex-1 flex-col gap-1 py-2 text-[11px]"
            } ${isActive ? "text-primary" : "text-muted hover:text-text"}`
          }
        >
          {({ isActive }) =>
            orientation === "row" ? (
              <>
                {isActive && (
                  <motion.span
                    layoutId="bottomnav-dot"
                    className="absolute top-0.5 h-1 w-1 rounded-full bg-primary"
                    transition={{ type: "spring", stiffness: 480, damping: 32 }}
                  />
                )}
                <motion.span
                  className="relative z-10 flex h-9 w-9 items-center justify-center rounded-full"
                  animate={{ y: isActive ? -3 : 0 }}
                  transition={{ type: "spring", stiffness: 500, damping: 24 }}
                  whileTap={{ scale: 0.8 }}
                >
                  {isActive && (
                    <motion.span
                      layoutId="bottomnav-active"
                      className="absolute inset-0 -z-10 rounded-full bg-primary/12"
                      transition={{ type: "spring", stiffness: 420, damping: 34 }}
                    />
                  )}
                  <item.icon size={20} strokeWidth={isActive ? 2.3 : 1.8} />
                </motion.span>
                <motion.span
                  className="relative z-10"
                  animate={{ opacity: isActive ? 1 : 0.85 }}
                  transition={{ duration: 0.15 }}
                >
                  {item.label}
                </motion.span>
              </>
            ) : (
              <>
                {isActive && (
                  <motion.span
                    layoutId="sidebar-active"
                    className="absolute inset-0 rounded-md bg-primary/10"
                    transition={{ type: "spring", stiffness: 420, damping: 34 }}
                  />
                )}
                <span className="relative z-10 flex items-center justify-center">
                  <item.icon size={20} strokeWidth={isActive ? 2.3 : 1.8} />
                </span>
                <span className="relative z-10">{item.label}</span>
              </>
            )
          }
        </NavLink>
      ))}
    </>
  );
}

export function AppShell() {
  const location = useLocation();

  return (
    <div className="mx-auto flex min-h-screen max-w-6xl">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col gap-1 border-l border-border bg-surface p-4 md:flex">
        <div className="mb-5 flex items-center justify-between px-1">
          <span className="bg-gradient-to-l from-primary to-accent bg-clip-text text-lg font-extrabold tracking-tight text-transparent">
            پنل کاربری
          </span>
        </div>
        <NavButtons orientation="col" />
        <div className="mt-auto flex flex-col gap-3 px-1 pt-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted">ظاهر</span>
            <ThemeToggle />
          </div>
          <AppVersion className="text-center" />
        </div>
      </aside>

      <div className="flex min-h-screen w-full flex-1 flex-col">
        <header className="sticky top-0 z-20 flex items-center justify-between border-b border-border bg-surface/90 px-4 py-3 backdrop-blur md:hidden">
          <span className="bg-gradient-to-l from-primary to-accent bg-clip-text text-base font-extrabold tracking-tight text-transparent">
            پنل کاربری
          </span>
          <ThemeToggle />
        </header>

        <main className="flex-1 px-4 pb-24 pt-4 md:pb-8">
          <AnimatePresence mode="wait" initial={false}>
            <PageTransition key={location.pathname}>
              <Outlet />
            </PageTransition>
          </AnimatePresence>
        </main>

        <nav className="safe-area-pb fixed inset-x-0 bottom-0 z-30 flex border-t border-border bg-surface/95 backdrop-blur md:hidden">
          <NavButtons orientation="row" />
        </nav>
      </div>
    </div>
  );
}
