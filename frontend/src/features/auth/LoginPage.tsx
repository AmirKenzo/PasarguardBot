import { useState } from "react";
import { motion } from "framer-motion";
import { Lock, Shield, ShoppingBag, Signal, Wallet } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { authApi } from "../../api/webapp";
import { Button, Input, MagicCard, SmokeyBackground, ShimmerButton, LanguageToggle } from "../../components/ui";
import { useAuth } from "../../context/AuthContext";

export default function LoginPage() {
  const { t } = useTranslation();
  const [loginMode, setLoginMode] = useState<"phone" | "apiKey">("phone");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [apiKey, setApiKey] = useState("");
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
      setError(err instanceof Error ? err.message : t("auth.networkError"));
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
        setError(t("auth.invalidCode"));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t("auth.networkError"));
    } finally {
      setLoading(false);
    }
  }

  async function handleApiKeyLogin(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await authApi.apiKeyLogin({ api_key: apiKey.trim() });
      if (res.session_token && res.user) {
        setToken(res.session_token);
        setUser(res.user);
        navigate("/", { replace: true });
      } else {
        setError(t("auth.invalidApiKey"));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t("auth.networkError"));
    } finally {
      setLoading(false);
    }
  }

  function toggleLoginMode() {
    setError("");
    setLoginMode((mode) => (mode === "phone" ? "apiKey" : "phone"));
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-bg p-4">
      <SmokeyBackground />
      <div className="pointer-events-none absolute -right-24 top-0 h-72 w-72 rounded-full bg-primary/15 blur-3xl" />
      <div className="pointer-events-none absolute -left-24 bottom-0 h-72 w-72 rounded-full bg-accent/15 blur-3xl" />

      <div className="absolute end-4 top-[calc(1rem+var(--tg-safe-area-top,0px)+var(--tg-content-safe-area-top,0px))]">
        <LanguageToggle />
      </div>

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
            <p className="text-xs font-medium uppercase tracking-[0.3em] text-muted">{t("auth.secureAccess")}</p>
            <h1 className="mt-3 text-4xl font-black text-text">{t("auth.accountPortal")}</h1>
            <p className="mt-4 max-w-md text-base leading-7 text-muted">
              {t("auth.accountDescription")}
            </p>
            <div className="mt-10 grid grid-cols-2 gap-3">
              <FeatureCard icon={Signal} title={t("auth.services")} text={t("auth.servicesDesc")} />
              <FeatureCard icon={ShoppingBag} title={t("auth.quickPurchase")} text={t("auth.quickPurchaseDesc")} />
              <FeatureCard icon={Wallet} title={t("auth.wallet")} text={t("auth.walletDesc")} />
              <FeatureCard icon={Shield} title={t("auth.secure")} text={t("auth.secureDesc")} />
            </div>
          </motion.section>

          <motion.section
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-2xl border border-border bg-surface p-6 shadow-lg sm:p-8"
          >
            <div className="mb-8 text-center">
              <h2 className="text-3xl font-black text-text">{t("auth.welcome")}</h2>
              <p className="mt-3 text-base text-muted">
                {loginMode === "apiKey" ? t("auth.apiKeySignIn") : otpSent ? t("auth.codeVerify") : t("auth.phoneSignIn")}
              </p>
            </div>

            {error && (
              <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm font-medium text-danger"
              >
                {error}
              </motion.div>
            )}

            {loginMode === "apiKey" ? (
              <form onSubmit={handleApiKeyLogin} className="mt-8 space-y-4">
                <div>
                  <label className="mb-2 block text-sm font-medium text-text">{t("auth.apiKeyLabel")}</label>
                  <Input
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder={t("auth.apiKeyPlaceholder")}
                    required
                    ltr
                    className="text-base"
                  />
                </div>

                <ShimmerButton type="submit" disabled={loading} className="mt-6 w-full py-3 text-base">
                  {loading ? t("auth.processing") : t("auth.verifySignIn")}
                </ShimmerButton>
              </form>
            ) : (
              <form onSubmit={otpSent ? handleOtpVerify : handleOtpStart} className="mt-8 space-y-4">
                <div>
                  <label className="mb-2 block text-sm font-medium text-text">{t("auth.phoneLabel")}</label>
                  <Input
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder={t("auth.phonePlaceholder")}
                    required
                    disabled={otpSent}
                    className="text-base"
                  />
                </div>

                {otpSent && (
                  <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
                    <label className="mb-2 block text-sm font-medium text-text">{t("auth.codeLabel")}</label>
                    <Input
                      value={code}
                      onChange={(e) => setCode(e.target.value)}
                      placeholder={t("auth.codePlaceholder")}
                      required
                      maxLength={6}
                      ltr
                      className="text-center text-lg tracking-widest"
                    />
                    <p className="mt-2 text-xs text-muted">{t("auth.codeHint")}</p>
                  </motion.div>
                )}

                <ShimmerButton type="submit" disabled={loading} className="mt-6 w-full py-3 text-base">
                  {loading
                    ? t("auth.processing")
                    : otpSent
                      ? t("auth.verifySignIn")
                      : t("auth.sendCode")}
                </ShimmerButton>

                {otpSent && (
                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                    <Button
                      type="button"
                      variant="ghost"
                      fullWidth
                      className="mt-2"
                      onClick={() => {
                        setOtpSent(false);
                        setCode("");
                        setError("");
                      }}
                    >
                      {t("auth.changePhone")}
                    </Button>
                  </motion.div>
                )}
              </form>
            )}

            <Button type="button" variant="ghost" fullWidth className="mt-2" onClick={toggleLoginMode}>
              {loginMode === "apiKey" ? t("auth.usePhoneInstead") : t("auth.useApiKeyInstead")}
            </Button>

            <p className="mt-6 text-center text-xs text-muted">
              {t("auth.security")}
            </p>
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
