import { useState } from "react";
import { motion } from "framer-motion";
import { Lock, Shield, ShoppingBag, Signal, Wallet } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { authApi } from "../../api/webapp";
import { Button, Input, MagicCard, SmokeyBackground, ShimmerButton } from "../../components/ui";
import { useAuth } from "../../context/AuthContext";

export default function LoginPage() {
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { setToken, setUser } = useAuth();
  const navigate = useNavigate();

  async function handleOtpStart(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await authApi.otpStart({ phone: phone.trim() });
      setOtpSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای شبکه");
    } finally {
      setLoading(false);
    }
  }

  async function handleOtpVerify(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await authApi.otpVerify({ phone: phone.trim(), code: code.trim() });
      if (res.session_token && res.user) {
        setToken(res.session_token);
        setUser(res.user);
        navigate("/", { replace: true });
      } else {
        setError("کد نامعتبر");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای شبکه");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-bg p-4">
      <SmokeyBackground />
      <div className="pointer-events-none absolute -right-24 top-0 h-72 w-72 rounded-full bg-primary/15 blur-3xl" />
      <div className="pointer-events-none absolute -left-24 bottom-0 h-72 w-72 rounded-full bg-accent/15 blur-3xl" />

      <div className="relative mx-auto flex min-h-screen max-w-5xl items-center justify-center">
        <div className="grid w-full gap-6 lg:grid-cols-[1.05fr_0.95fr]">
          <motion.section
            initial={{ opacity: 0, x: 24 }}
            animate={{ opacity: 1, x: 0 }}
            className="hidden overflow-hidden rounded-2xl border border-border bg-surface p-8 shadow-lg lg:block"
          >
            <div className="mb-8 inline-flex rounded-xl bg-primary/10 p-3 text-primary">
              <Lock size={28} />
            </div>
            <p className="text-xs font-medium uppercase tracking-[0.3em] text-muted">Secure WebApp</p>
            <h1 className="mt-3 text-3xl font-black text-text">ورود به پنل کاربری</h1>
            <p className="mt-4 max-w-md text-sm leading-7 text-muted">
              مدیریت سرویس‌ها، تمدید، خرید کانفیگ و شارژ کیف پول را با رابط سریع و امن انجام بده.
            </p>
            <div className="mt-10 grid grid-cols-2 gap-3">
              <FeatureCard icon={Signal} title="سرویس‌ها" text="وضعیت، لینک و مصرف" />
              <FeatureCard icon={ShoppingBag} title="خرید سریع" text="پلن، تخفیف و تحویل" />
              <FeatureCard icon={Wallet} title="کیف پول" text="شارژ دستی، خودکار و کریپتو" />
              <FeatureCard icon={Shield} title="امن" text="ورود با کد یک‌بارمصرف تلگرام" />
            </div>
          </motion.section>

          <motion.section
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-2xl border border-border bg-surface p-5 shadow-lg sm:p-7"
          >
            <div className="mb-6 text-center">
              <h2 className="text-2xl font-black text-text">خوش برگشتی</h2>
              <p className="mt-2 text-sm text-muted">
                شماره تلفن حساب تلگرامت رو وارد کن تا کد ورود برات ارسال شود.
              </p>
            </div>

            {error && (
              <div className="mt-4 rounded-md border border-danger/25 bg-danger/10 px-4 py-3 text-sm text-danger">
                {error}
              </div>
            )}

            <form onSubmit={otpSent ? handleOtpVerify : handleOtpStart} className="mt-6 space-y-4">
              <Input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="شماره تلفن"
                required
                disabled={otpSent}
              />
              {otpSent && (
                <Input
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="کد ۶ رقمی"
                  required
                  maxLength={6}
                  ltr
                />
              )}
              <ShimmerButton type="submit" disabled={loading} className="w-full">
                {otpSent ? "تایید" : "ارسال کد"}
              </ShimmerButton>
              {otpSent && (
                <Button
                  type="button"
                  variant="ghost"
                  fullWidth
                  onClick={() => {
                    setOtpSent(false);
                    setCode("");
                    setError("");
                  }}
                >
                  تغییر شماره
                </Button>
              )}
            </form>
          </motion.section>
        </div>
      </div>
    </div>
  );
}

function FeatureCard({
  icon: Icon,
  title,
  text,
}: {
  icon: typeof Lock;
  title: string;
  text: string;
}) {
  return (
    <MagicCard className="bg-surface-2 p-4">
      <Icon size={22} className="text-primary" />
      <p className="mt-3 font-bold text-text">{title}</p>
      <p className="mt-1 text-xs text-muted">{text}</p>
    </MagicCard>
  );
}
