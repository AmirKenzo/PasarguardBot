import Link from 'next/link';
import {
  ArrowLeft,
  BookOpenText,
  Boxes,
  CreditCard,
  DownloadCloud,
  HeartHandshake,
  KeyRound,
  LayoutDashboard,
  PanelTop,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  WalletCards,
} from 'lucide-react';
import { botVersion } from '@/lib/version';
import type { LucideIcon } from 'lucide-react';

const chips = [
  { href: '/docs/getting-started/configuration', label: 'پیکربندی .env', icon: Boxes },
  { href: '/docs/user/buy', label: 'خرید سرویس', icon: ShoppingBag },
  { href: '/docs/admin/panels', label: 'منوی پنل‌ها', icon: PanelTop },
  { href: '/docs/support', label: 'حمایت مالی', icon: HeartHandshake },
];

const paths: {
  href: string;
  title: string;
  description: string;
  icon: LucideIcon;
}[] = [
  {
    href: '/docs/getting-started/install',
    title: 'شروع سریع',
    description: 'نصب لینوکس، تنظیم env، پورت‌ها و منوی مدیریت سرور.',
    icon: DownloadCloud,
  },
  {
    href: '/docs/user',
    title: 'راهنمای کاربر',
    description: 'توضیح دکمه‌های منوی اصلی: خرید، سرویس‌ها، شارژ و بیشتر.',
    icon: BookOpenText,
  },
  {
    href: '/docs/admin',
    title: 'پنل ادمین',
    description: 'راهنمای بخش‌های مدیریت: درگاه، پنل‌ها، پلن‌ها و تنظیمات.',
    icon: ShieldCheck,
  },
  {
    href: '/docs/support',
    title: 'حمایت مالی',
    description: 'اگر پروژه برایتان مفید بوده، می‌توانید داوطلبانه حمایت کنید.',
    icon: HeartHandshake,
  },
];

const highlights = [
  {
    href: '/docs/user/my-services',
    title: 'سرویس‌های من',
    description: 'تمدید، حجم اضافه، QR، لینک ساب و مدیریت کانفیگ.',
    icon: KeyRound,
  },
  {
    href: '/docs/admin/gateway',
    title: 'تنظیمات درگاه',
    description: 'کارت‌به‌کارت، کیف پول ارزی، بونوس و تایید خودکار.',
    icon: CreditCard,
  },
  {
    href: '/docs/admin/panels',
    title: 'منوی پنل‌ها',
    description: 'افزودن پنل پاسارگارد، فروش، تست و نمایندگی.',
    icon: PanelTop,
  },
  {
    href: '/docs/user/balance',
    title: 'افزایش موجودی',
    description: 'شارژ کیف پول با کارت‌به‌کارت یا پرداخت ارزی.',
    icon: WalletCards,
  },
];

function IconBadge({ icon: Icon }: { icon: LucideIcon }) {
  return (
    <span className="mb-3 inline-flex size-10 items-center justify-center rounded-xl bg-fd-primary/12 text-fd-primary ring-1 ring-fd-primary/15">
      <Icon className="size-5" strokeWidth={1.75} />
    </span>
  );
}

export default function HomePage() {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-10 sm:px-6 lg:px-8">
      <section className="mb-10">
        <div className="mb-4 inline-flex items-center gap-2 rounded-full border bg-fd-card/80 px-3 py-1 text-xs text-fd-muted-foreground shadow-sm">
          <Sparkles className="size-3.5 text-fd-primary" />
          <span className="font-semibold text-fd-primary" dir="ltr">
            v{botVersion}
          </span>
          <span className="text-fd-border">|</span>
          مستندات PasarguardBot
        </div>
        <h1 className="max-w-3xl text-3xl font-bold tracking-tight sm:text-4xl lg:text-5xl">
          PasarguardBot. فروش وی‌پی‌ان داخل تلگرام، تمیز و کامل.
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-8 text-fd-muted-foreground sm:text-lg">
          ربات فروش، تمدید، شارژ کیف پول و پشتیبانی کاربران روی پنل پاسارگارد. ادمین از همان ربات
          پنل‌ها، پلن‌ها، پرداخت‌ها و نمایندگان را مدیریت می‌کند.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/docs/getting-started/install"
            className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-fd-primary px-5 text-sm font-semibold text-fd-primary-foreground transition hover:opacity-90"
          >
            شروع نصب
            <ArrowLeft className="size-4" />
          </Link>
          <Link
            href="/docs/user"
            className="inline-flex h-11 items-center justify-center rounded-xl border bg-fd-card px-5 text-sm font-semibold transition hover:bg-fd-accent"
          >
            راهنمای کاربر
          </Link>
          <Link
            href="/docs/admin"
            className="inline-flex h-11 items-center justify-center rounded-xl border bg-fd-card px-5 text-sm font-semibold transition hover:bg-fd-accent"
          >
            پنل ادمین
          </Link>
        </div>
        <div className="mt-5 flex flex-wrap gap-2">
          {chips.map((chip) => (
            <Link
              key={chip.href}
              href={chip.href}
              className="inline-flex items-center gap-1.5 rounded-full border bg-fd-card/70 px-3 py-1.5 text-xs text-fd-muted-foreground transition hover:border-fd-primary hover:bg-fd-accent hover:text-fd-foreground"
            >
              <chip.icon className="size-3.5 text-fd-primary" strokeWidth={1.75} />
              {chip.label}
            </Link>
          ))}
        </div>
      </section>

      <section className="mb-10 rounded-2xl border bg-gradient-to-b from-fd-primary/10 via-fd-card/40 to-transparent p-5 sm:p-6">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-base font-semibold">نمای کلی ربات</h2>
          <span className="text-xs text-fd-muted-foreground" dir="ltr">
            v{botVersion}
          </span>
        </div>
        <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-fd-primary/15 px-2.5 py-1 text-xs font-semibold text-fd-primary">
          <span className="size-1.5 rounded-full bg-emerald-400" />
          نسخه فعلی آماده انتشار
        </div>
        <div className="mb-4 grid gap-3 sm:grid-cols-3">
          {[
            { value: 'User', label: 'منوی کاربر و خرید', icon: BookOpenText },
            { value: 'Admin', label: 'پنل مدیریت کامل', icon: ShieldCheck },
            { value: 'Docker', label: 'نصب یک‌خطی لینوکس', icon: DownloadCloud },
          ].map((metric) => (
            <div key={metric.value} className="rounded-xl border bg-fd-card/80 p-4">
              <metric.icon className="mb-2 size-4 text-fd-primary" strokeWidth={1.75} />
              <div className="text-lg font-bold" dir="ltr">
                {metric.value}
              </div>
              <div className="mt-1 text-xs text-fd-muted-foreground">{metric.label}</div>
            </div>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          {['Telethon Bot', 'PasarGuard Panel', 'Wallet & Gateway'].map((item) => (
            <div
              key={item}
              className="inline-flex items-center gap-2 rounded-full border bg-fd-secondary/40 px-3 py-1 text-xs text-fd-muted-foreground"
            >
              <span className="size-1.5 rounded-full bg-emerald-400" />
              {item}
            </div>
          ))}
        </div>
      </section>

      <section className="mb-10">
        <h2 className="mb-4 text-lg font-semibold">مسیرهای اصلی</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {paths.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-2xl border bg-fd-card p-5 transition hover:-translate-y-0.5 hover:border-fd-primary hover:shadow-sm"
            >
              <IconBadge icon={item.icon} />
              <h3 className="mb-1 font-semibold">{item.title}</h3>
              <p className="text-sm leading-7 text-fd-muted-foreground">{item.description}</p>
            </Link>
          ))}
        </div>
      </section>

      <section>
        <div className="mb-4 flex items-center gap-2">
          <LayoutDashboard className="size-4 text-fd-primary" />
          <h2 className="text-lg font-semibold">بخش‌های پرکاربرد</h2>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          {highlights.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-2xl border bg-fd-card p-5 transition hover:-translate-y-0.5 hover:border-fd-primary hover:shadow-sm"
            >
              <IconBadge icon={item.icon} />
              <h3 className="mb-1 font-semibold">{item.title}</h3>
              <p className="text-sm leading-7 text-fd-muted-foreground">{item.description}</p>
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}
