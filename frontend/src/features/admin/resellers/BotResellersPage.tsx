import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AlertTriangle, Bot, Check, Inbox, Package, Pause, Play, Plus, Power, Trash2, UserPlus, Users, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button, ErrorState, Input, Skeleton } from "../../../components/ui";
import { panelBotResellersApi } from "../../../api/panel";
import { formatBytes, formatNumber, formatToman, formatUnixDate } from "../../../lib/format";
import type { BotGrantRow, BotGrantTerms, BotResellerRow, BotServiceRow } from "../../../types/panel";
import { usePanelAction, usePanelQuery } from "../../../queries/usePanelApi";
import { Card, Chips, Dialog, Empty, Header, PageTitle, Pill, TelegramName, Toggle } from "./botResellerUi";

type Section = "requests" | "resellers" | "services";
const INVALIDATE = [["bot-resellers"]];

const STATUS_TONE: Record<string, "success" | "warning" | "danger" | "muted"> = {
  active: "success",
  frozen: "danger",
  suspended: "warning",
  pending: "warning",
  approved: "success",
  rejected: "danger",
  revoked: "muted",
};

function num(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const n = Number(trimmed);
  return Number.isFinite(n) && n >= 0 ? n : null;
}

const SECTIONS: Section[] = ["requests", "resellers", "services"];

export default function BotResellersPage() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const fromUrl = searchParams.get("section") as Section | null;
  const section: Section = fromUrl && SECTIONS.includes(fromUrl) ? fromUrl : "requests";
  const setSection = (value: Section) => setSearchParams({ section: value }, { replace: true });
  const requests = usePanelQuery(["bot-resellers", "requests"], (auth) => panelBotResellersApi.listRequests(auth));

  return (
    <div className="space-y-4">
      <PageTitle title={t("panel.botResellers.title")} subtitle={t("panel.botResellers.subtitle")} />
      <SaleSwitchCard />
      <Chips<Section>
        id="bot-reseller-section"
        value={section}
        onChange={setSection}
        items={[
          { value: "requests", label: t("panel.botResellers.requests"), count: requests.data?.requests.length },
          { value: "resellers", label: t("panel.botResellers.resellers") },
          { value: "services", label: t("panel.botResellers.services") },
        ]}
      />
      {section === "requests" && <RequestsSection />}
      {section === "resellers" && <ResellersSection />}
      {section === "services" && <ServicesSection />}
    </div>
  );
}

function MiniSwitch({ on, onChange, busy, label }: { on: boolean; onChange: (v: boolean) => void; busy?: boolean; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      disabled={busy}
      onClick={(e) => {
        e.stopPropagation();
        onChange(!on);
      }}
      className={`relative h-6 w-11 shrink-0 rounded-full transition-colors disabled:opacity-60 ${on ? "bg-success" : "bg-border"}`}
    >
      <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${on ? "end-0.5" : "start-0.5"}`} />
    </button>
  );
}

function SaleSwitchCard() {
  const { t } = useTranslation();
  const query = usePanelQuery(["bot-resellers", "settings"], (auth) => panelBotResellersApi.readSettings(auth));
  const save = usePanelAction(panelBotResellersApi.saveSettings, { invalidate: INVALIDATE });
  const data = query.data;
  if (!data) return query.isLoading ? <Skeleton className="h-20 w-full rounded-2xl" /> : null;

  const on = data.settings.sale_mode;
  const visible = on && data.global_sale_mode && data.services_on_sale > 0;
  const warning = !on ? null : !data.global_sale_mode ? t("panel.botResellers.sale.globalOff") : data.services_on_sale === 0 ? t("panel.botResellers.sale.noServices") : null;

  return (
    <div className={`rounded-3xl p-4 ring-1 ring-inset transition-colors ${visible ? "bg-success/10 ring-success/30" : "bg-surface-2/60 ring-border"}`}>
      <div className="flex items-center gap-3">
        <span className={`grid h-11 w-11 shrink-0 place-items-center rounded-2xl ${visible ? "bg-success/20 text-success" : "bg-surface text-muted"}`}>
          <Power size={20} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-black">{t("panel.botResellers.sale.title")}</p>
          <p className="text-xs text-muted">
            {visible ? t("panel.botResellers.sale.visible", { count: data.services_on_sale }) : t("panel.botResellers.sale.hidden")}
          </p>
        </div>
        <MiniSwitch on={on} busy={save.isPending} label={t("panel.botResellers.sale.title")} onChange={(value) => save.mutate({ settings: { sale_mode: value } })} />
      </div>
      {warning && (
        <p className="mt-3 flex items-center gap-1.5 rounded-xl bg-warning/10 px-3 py-2 text-xs text-warning">
          <AlertTriangle size={14} className="shrink-0" />
          {warning}
        </p>
      )}
      <p className="mt-2 text-[11px] text-muted">{t("panel.botResellers.sale.hint")}</p>
    </div>
  );
}

function TermsFields({ value, onChange, defaults }: { value: Record<keyof BotGrantTerms, string>; onChange: (v: Record<keyof BotGrantTerms, string>) => void; defaults?: BotGrantRow }) {
  const { t } = useTranslation();
  const field = (key: keyof BotGrantTerms, label: string, placeholder?: number) => (
    <Input
      dense
      label={label}
      inputMode="decimal"
      ltr
      value={value[key]}
      placeholder={placeholder != null ? String(placeholder) : t("panel.botResellers.serviceDefault")}
      onChange={(e) => onChange({ ...value, [key]: e.target.value })}
    />
  );
  return (
    <div className="grid grid-cols-2 gap-2">
      {field("price_per_gb", t("panel.botResellers.pricePerGb"), defaults?.price_per_gb)}
      {field("max_users", t("panel.botResellers.maxUsers"), defaults?.max_users)}
      {field("max_user_gb", t("panel.botResellers.maxUserGb"), defaults?.max_user_gb)}
      {field("max_user_days", t("panel.botResellers.maxUserDays"), defaults?.max_user_days)}
    </div>
  );
}

const EMPTY_TERMS: Record<keyof BotGrantTerms, string> = { price_per_gb: "", max_users: "", max_user_gb: "", max_user_days: "" };

function toTerms(value: Record<keyof BotGrantTerms, string>): BotGrantTerms {
  return {
    price_per_gb: num(value.price_per_gb),
    max_users: num(value.max_users),
    max_user_gb: num(value.max_user_gb),
    max_user_days: num(value.max_user_days),
  };
}

function RequestsSection() {
  const { t } = useTranslation();
  const query = usePanelQuery(["bot-resellers", "requests"], (auth) => panelBotResellersApi.listRequests(auth));
  const [manual, setManual] = useState(false);

  return (
    <Card>
      <Header
        icon={Inbox}
        title={t("panel.botResellers.requests")}
        hint={t("panel.botResellers.requestsHint")}
        action={
          <Button size="sm" variant="secondary" onClick={() => setManual(true)}>
            <UserPlus size={14} />
            {t("panel.botResellers.grantManual")}
          </Button>
        }
      />
      {query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : query.isLoading ? (
        <Skeleton className="h-32 w-full rounded-2xl" />
      ) : query.data?.requests.length ? (
        <div className="grid gap-3 md:grid-cols-2">
          {query.data.requests.map((row) => (
            <RequestCard key={row.id} row={row} />
          ))}
        </div>
      ) : (
        <Empty icon={Inbox} title={t("panel.botResellers.noRequests")} />
      )}
      <ManualGrantDialog open={manual} onClose={() => setManual(false)} />
    </Card>
  );
}

function RequestCard({ row }: { row: BotGrantRow }) {
  const { t } = useTranslation();
  const [terms, setTerms] = useState(EMPTY_TERMS);
  const [reason, setReason] = useState("");
  const [rejecting, setRejecting] = useState(false);
  const approve = usePanelAction(panelBotResellersApi.approve, { invalidate: INVALIDATE });
  const reject = usePanelAction(panelBotResellersApi.reject, { invalidate: INVALIDATE });

  return (
    <div className="space-y-3 rounded-2xl bg-surface-2/50 p-3 ring-1 ring-inset ring-border">
      <div className="flex items-center justify-between gap-2">
        <TelegramName id={row.telegram_id} showId />
        <Pill tone="primary">{row.service_name}</Pill>
      </div>
      <p className="text-xs text-muted">
        {t("panel.botResellers.balance")}: <b className="text-text">{formatToman(row.balance)}</b> · {formatUnixDate(row.requested_at)}
      </p>
      <TermsFields value={terms} onChange={setTerms} defaults={row} />
      {rejecting && <Input dense label={t("panel.botResellers.rejectReason")} value={reason} onChange={(e) => setReason(e.target.value)} />}
      <div className="grid grid-cols-2 gap-2">
        <Button size="sm" loading={approve.isPending} onClick={() => approve.mutate({ grant_id: row.id, terms: toTerms(terms) })}>
          <Check size={14} />
          {t("panel.botResellers.approve")}
        </Button>
        <Button
          size="sm"
          variant="danger"
          loading={reject.isPending}
          onClick={() => (rejecting ? reject.mutate({ grant_id: row.id, reason: reason || null }) : setRejecting(true))}
        >
          <X size={14} />
          {rejecting ? t("panel.botResellers.rejectConfirm") : t("panel.botResellers.reject")}
        </Button>
      </div>
    </div>
  );
}

function ManualGrantDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useTranslation();
  const services = usePanelQuery(["bot-resellers", "services"], (auth) => panelBotResellersApi.listServices(auth), { enabled: open });
  const [telegramId, setTelegramId] = useState("");
  const [serviceId, setServiceId] = useState<number | null>(null);
  const [terms, setTerms] = useState(EMPTY_TERMS);
  const grant = usePanelAction(panelBotResellersApi.grantManually, { invalidate: INVALIDATE });
  const rows = services.data?.services || [];

  return (
    <Dialog open={open} onClose={onClose} icon={UserPlus} title={t("panel.botResellers.grantManual")} subtitle={t("panel.botResellers.grantManualHint")}>
      <div className="space-y-3">
        <Input label={t("panel.botResellers.telegramId")} inputMode="numeric" ltr value={telegramId} onChange={(e) => setTelegramId(e.target.value)} />
        <div className="flex flex-wrap gap-2">
          {rows.map((s) => (
            <button key={s.id} type="button" onClick={() => setServiceId(s.id)} className={`rounded-xl px-3 py-2 text-xs font-bold ring-1 ring-inset ${serviceId === s.id ? "bg-primary/15 text-primary ring-primary/40" : "ring-border"}`}>
              {s.name} · {formatNumber(s.price_per_gb)}
            </button>
          ))}
        </div>
        <TermsFields value={terms} onChange={setTerms} />
        <Button
          fullWidth
          loading={grant.isPending}
          disabled={!serviceId || !Number(telegramId)}
          onClick={() => grant.mutate({ telegram_id: Number(telegramId), service_id: serviceId as number, terms: toTerms(terms) }, { onSuccess: onClose })}
        >
          {t("panel.botResellers.grant")}
        </Button>
      </div>
    </Dialog>
  );
}

function ResellersSection() {
  const { t } = useTranslation();
  const query = usePanelQuery(["bot-resellers", "list"], (auth) => panelBotResellersApi.listResellers(auth));
  const [open, setOpen] = useState<number | null>(null);
  const rows = query.data?.resellers || [];

  return (
    <Card>
      <Header icon={Users} title={t("panel.botResellers.resellers")} hint={t("panel.botResellers.resellersHint")} />
      {query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : query.isLoading ? (
        <Skeleton className="h-32 w-full rounded-2xl" />
      ) : rows.length ? (
        <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
          {rows.map((row) => (
            <ResellerCard key={row.id} row={row} onOpen={() => setOpen(row.id)} />
          ))}
        </div>
      ) : (
        <Empty icon={Bot} title={t("panel.botResellers.noResellers")} />
      )}
      <ResellerDialog id={open} onClose={() => setOpen(null)} />
    </Card>
  );
}

function ResellerCard({ row, onOpen }: { row: BotResellerRow; onOpen: () => void }) {
  const { t } = useTranslation();
  return (
    <button type="button" onClick={onOpen} className="space-y-2 rounded-2xl bg-surface-2/50 p-3 text-start ring-1 ring-inset ring-border transition-colors hover:ring-primary/40">
      <div className="flex items-center justify-between gap-2">
        <TelegramName id={row.telegram_id} showId />
        <Pill tone={STATUS_TONE[row.status] || "muted"} dot>
          {t(`panel.botResellers.status.${row.status}`)}
        </Pill>
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
        <span>
          {t("panel.botResellers.balance")}: <b className={row.balance <= 0 ? "text-danger" : "text-text"}>{formatToman(row.balance)}</b>
        </span>
        <span>
          {t("panel.botResellers.users")}: <b className="text-text">{formatNumber(row.users)}</b>
        </span>
        <span>
          24h: <b className="text-text">{formatBytes(row.usage_24h_bytes, 2)}</b> · {formatToman(row.usage_24h_amount)}
        </span>
      </div>
      <p className="truncate text-xs text-muted">{row.services.join(" · ") || "—"}</p>
    </button>
  );
}

function ResellerDialog({ id, onClose }: { id: number | null; onClose: () => void }) {
  const { t } = useTranslation();
  const query = usePanelQuery(["bot-resellers", "detail", id], (auth) => panelBotResellersApi.detail({ ...auth, id: id as number }), { enabled: id != null });
  const suspend = usePanelAction(panelBotResellersApi.suspend, { invalidate: INVALIDATE });
  const unsuspend = usePanelAction(panelBotResellersApi.unsuspend, { invalidate: INVALIDATE });
  const removeUser = usePanelAction(panelBotResellersApi.deleteUser, { invalidate: INVALIDATE });
  const [confirmUser, setConfirmUser] = useState<number | null>(null);
  const reseller = query.data?.reseller;

  return (
    <Dialog open={id != null} onClose={onClose} icon={Bot} title={t("panel.botResellers.detail")} wide>
      {!reseller ? (
        query.isError ? <ErrorState message={query.error.message} /> : <Skeleton className="h-40 w-full rounded-2xl" />
      ) : (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <TelegramName id={reseller.telegram_id} showId />
            <div className="flex items-center gap-2">
              <Pill tone={STATUS_TONE[reseller.status] || "muted"} dot>
                {t(`panel.botResellers.status.${reseller.status}`)}
              </Pill>
              {reseller.status === "suspended" ? (
                <Button size="sm" loading={unsuspend.isPending} onClick={() => unsuspend.mutate({ id: reseller.id })}>
                  <Play size={14} />
                  {t("panel.botResellers.unsuspend")}
                </Button>
              ) : (
                <Button size="sm" variant="danger" loading={suspend.isPending} onClick={() => suspend.mutate({ id: reseller.id })}>
                  <Pause size={14} />
                  {t("panel.botResellers.suspend")}
                </Button>
              )}
            </div>
          </div>
          <p className="text-xs text-muted">
            {t("panel.botResellers.balance")}: <b className="text-text">{formatToman(reseller.balance)}</b> · 24h: {formatBytes(reseller.usage_24h_bytes, 2)} · {formatToman(reseller.usage_24h_amount)}
          </p>

          <NamingCard reseller={reseller} />

          <div className="space-y-2">
            <h3 className="text-sm font-black">{t("panel.botResellers.grants")}</h3>
            {query.data?.grants.map((grant) => (
              <GrantRow key={grant.id} grant={grant} />
            ))}
          </div>

          <div className="space-y-2">
            <h3 className="text-sm font-black">
              {t("panel.botResellers.users")} ({formatNumber(query.data?.users.length || 0)})
            </h3>
            <div className="max-h-80 divide-y divide-border overflow-y-auto rounded-2xl ring-1 ring-inset ring-border">
              {query.data?.users.map((user) => (
                <div key={user.id} className="flex items-center justify-between gap-2 px-3 py-2 text-xs">
                  <div className="min-w-0">
                    <p className="truncate font-bold" dir="ltr">
                      {user.username}
                    </p>
                    <p className="truncate text-muted">
                      {user.service_name} · {formatBytes(user.billed_bytes, 2)} · {formatToman(user.cost)}
                      {user.disabled_by ? ` · ${t(`panel.botResellers.disabledBy.${user.disabled_by}`)}` : ""}
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant={confirmUser === user.id ? "danger" : "ghost"}
                    loading={removeUser.isPending && confirmUser === user.id}
                    onClick={() => (confirmUser === user.id ? removeUser.mutate({ user_id: user.id }) : setConfirmUser(user.id))}
                  >
                    <Trash2 size={14} />
                  </Button>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </Dialog>
  );
}

type AffixMode = "none" | "id" | "custom";
const TELEGRAM_ID = "{id}";

function affixMode(value: string): AffixMode {
  if (!value) return "none";
  return value === TELEGRAM_ID ? "id" : "custom";
}

function AffixField({ label, id, value, onChange }: { label: string; id: string; value: string; onChange: (v: string) => void }) {
  const { t } = useTranslation();
  const [mode, setMode] = useState<AffixMode>(affixMode(value));
  const [custom, setCustom] = useState(affixMode(value) === "custom" ? value : "");
  const pick = (next: AffixMode) => {
    setMode(next);
    onChange(next === "none" ? "" : next === "id" ? TELEGRAM_ID : custom);
  };
  return (
    <div className="space-y-2">
      <p className="text-xs font-bold text-muted">{label}</p>
      <Chips<AffixMode>
        id={id}
        value={mode}
        onChange={pick}
        items={[
          { value: "none", label: t("panel.botResellers.naming.none") },
          { value: "id", label: t("panel.botResellers.naming.telegramId") },
          { value: "custom", label: t("panel.botResellers.naming.custom") },
        ]}
      />
      {mode === "custom" && (
        <Input
          dense
          ltr
          maxLength={12}
          value={custom}
          placeholder="shop"
          onChange={(e) => {
            const next = e.target.value.toLowerCase().replace(/[^a-z0-9]/g, "");
            setCustom(next);
            onChange(next);
          }}
        />
      )}
    </div>
  );
}

function NamingCard({ reseller }: { reseller: BotResellerRow }) {
  const { t } = useTranslation();
  const [prefix, setPrefix] = useState(reseller.username_prefix);
  const [suffix, setSuffix] = useState(reseller.username_suffix);
  const save = usePanelAction(panelBotResellersApi.setNaming, { invalidate: INVALIDATE });
  const resolve = (value: string) => (value === TELEGRAM_ID ? String(reseller.telegram_id) : value);
  const example = [resolve(prefix), "ali", resolve(suffix)].filter(Boolean).join("_");
  const dirty = prefix !== reseller.username_prefix || suffix !== reseller.username_suffix;

  return (
    <div className="space-y-3 rounded-2xl bg-surface-2/50 p-3 ring-1 ring-inset ring-border">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-black">{t("panel.botResellers.naming.title")}</h3>
        <span className="rounded-full bg-surface px-2.5 py-1 font-mono text-xs font-bold text-primary ring-1 ring-inset ring-border" dir="ltr">
          {example}
        </span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <AffixField id={`brs-prefix-${reseller.id}`} label={t("panel.botResellers.naming.prefix")} value={prefix} onChange={setPrefix} />
        <AffixField id={`brs-suffix-${reseller.id}`} label={t("panel.botResellers.naming.suffix")} value={suffix} onChange={setSuffix} />
      </div>
      <p className="text-[11px] text-muted">{t("panel.botResellers.naming.hint")}</p>
      {dirty && (
        <Button size="sm" loading={save.isPending} onClick={() => save.mutate({ id: reseller.id, username_prefix: prefix, username_suffix: suffix })}>
          {t("panel.botResellers.save")}
        </Button>
      )}
    </div>
  );
}

function GrantRow({ grant }: { grant: BotGrantRow }) {
  const { t } = useTranslation();
  const [editing, setEditing] = useState(false);
  const [confirmRevoke, setConfirmRevoke] = useState(false);
  const [terms, setTerms] = useState(EMPTY_TERMS);
  const save = usePanelAction(panelBotResellersApi.updateTerms, { invalidate: INVALIDATE });
  const revoke = usePanelAction(panelBotResellersApi.revoke, { invalidate: INVALIDATE });

  const startEdit = () => {
    const own = grant.own_terms;
    setTerms({
      price_per_gb: own.price_per_gb != null ? String(own.price_per_gb) : "",
      max_users: own.max_users != null ? String(own.max_users) : "",
      max_user_gb: own.max_user_gb != null ? String(own.max_user_gb) : "",
      max_user_days: own.max_user_days != null ? String(own.max_user_days) : "",
    });
    setEditing(true);
  };

  return (
    <div className="space-y-2 rounded-2xl bg-surface-2/50 p-3 ring-1 ring-inset ring-border">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <b className="text-sm">{grant.service_name}</b>
          <Pill tone={STATUS_TONE[grant.status] || "muted"}>{t(`panel.botResellers.status.${grant.status}`)}</Pill>
        </div>
        <span className="text-xs text-muted">
          {formatNumber(grant.price_per_gb)} / GB · {formatNumber(grant.users)}
          {grant.max_users ? `/${formatNumber(grant.max_users)}` : ""} {t("panel.botResellers.users")}
        </span>
      </div>
      {editing ? (
        <>
          <TermsFields value={terms} onChange={setTerms} />
          <div className="grid grid-cols-2 gap-2">
            <Button size="sm" variant="secondary" onClick={() => setEditing(false)}>
              {t("panel.botResellers.cancel")}
            </Button>
            <Button size="sm" loading={save.isPending} onClick={() => save.mutate({ grant_id: grant.id, terms: toTerms(terms) }, { onSuccess: () => setEditing(false) })}>
              {t("panel.botResellers.save")}
            </Button>
          </div>
        </>
      ) : (
        grant.status === "approved" && (
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="secondary" onClick={startEdit}>
              {t("panel.botResellers.editTerms")}
            </Button>
            <Button size="sm" variant="danger" loading={revoke.isPending} onClick={() => (confirmRevoke ? revoke.mutate({ grant_id: grant.id }) : setConfirmRevoke(true))}>
              {confirmRevoke ? t("panel.botResellers.revokeConfirm", { count: grant.users }) : t("panel.botResellers.revoke")}
            </Button>
          </div>
        )
      )}
    </div>
  );
}

function ServicesSection() {
  const { t } = useTranslation();
  const query = usePanelQuery(["bot-resellers", "services"], (auth) => panelBotResellersApi.listServices(auth));
  const [editing, setEditing] = useState<BotServiceRow | "new" | null>(null);
  const toggle = usePanelAction(panelBotResellersApi.toggleService, { invalidate: INVALIDATE });

  return (
    <Card>
      <Header
        icon={Package}
        title={t("panel.botResellers.services")}
        hint={t("panel.botResellers.servicesHint")}
        action={
          <Button size="sm" onClick={() => setEditing("new")}>
            <Plus size={14} />
            {t("panel.botResellers.newService")}
          </Button>
        }
      />
      {query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : query.isLoading ? (
        <Skeleton className="h-32 w-full rounded-2xl" />
      ) : query.data?.services.length ? (
        <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
          {query.data.services.map((service) => (
            <div
              key={service.id}
              role="button"
              tabIndex={0}
              onClick={() => setEditing(service)}
              onKeyDown={(e) => e.key === "Enter" && setEditing(service)}
              className={`cursor-pointer space-y-1.5 rounded-2xl p-3 text-start ring-1 ring-inset transition-colors hover:ring-primary/40 ${service.sale_enabled ? "bg-surface-2/50 ring-border" : "bg-surface-2/20 ring-border/60 opacity-75"}`}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex min-w-0 items-center gap-2">
                  <b className="truncate text-sm">{service.name}</b>
                  <Pill tone={service.sale_enabled ? "success" : "muted"}>{service.sale_enabled ? t("panel.botResellers.onSale") : t("panel.botResellers.offSale")}</Pill>
                </div>
                <MiniSwitch
                  on={service.sale_enabled}
                  busy={toggle.isPending && toggle.variables?.id === service.id}
                  label={t("panel.botResellers.onSale")}
                  onChange={(value) => toggle.mutate({ id: service.id, sale_enabled: value })}
                />
              </div>
              <p className="text-xs text-muted">
                {service.panel_name} · {formatNumber(service.price_per_gb)} / GB · {formatNumber(service.resellers)} {t("panel.botResellers.resellersCount")}
              </p>
            </div>
          ))}
        </div>
      ) : (
        <Empty icon={Package} title={t("panel.botResellers.noServices")} hint={t("panel.botResellers.noServicesHint")} />
      )}
      {editing && <ServiceDialog service={editing === "new" ? null : editing} panels={query.data?.panels || []} onClose={() => setEditing(null)} />}
    </Card>
  );
}

function ServiceDialog({ service, panels, onClose }: { service: BotServiceRow | null; panels: { code: number; name: string }[]; onClose: () => void }) {
  const { t } = useTranslation();
  const [panelCode, setPanelCode] = useState<number | null>(service?.panel_code ?? panels[0]?.code ?? null);
  const [name, setName] = useState(service?.name || "");
  const [description, setDescription] = useState(service?.description || "");
  const [groupIds, setGroupIds] = useState<number[]>(service?.group_ids || []);
  const [price, setPrice] = useState(service ? String(service.price_per_gb) : "");
  const [maxUsers, setMaxUsers] = useState(service ? String(service.max_users) : "0");
  const [maxGb, setMaxGb] = useState(service ? String(service.max_user_gb) : "0");
  const [maxDays, setMaxDays] = useState(service ? String(service.max_user_days) : "0");
  const [onSale, setOnSale] = useState(service?.sale_enabled ?? true);
  const groups = usePanelQuery(["bot-resellers", "groups", panelCode], (auth) => panelBotResellersApi.panelGroups({ ...auth, panel_code: panelCode as number }), { enabled: panelCode != null });
  const save = usePanelAction(panelBotResellersApi.saveService, { invalidate: INVALIDATE });

  const toggleGroup = (id: number) => setGroupIds((prev) => (prev.includes(id) ? prev.filter((g) => g !== id) : [...prev, id]));

  return (
    <Dialog open onClose={onClose} icon={Package} title={service ? t("panel.botResellers.editService") : t("panel.botResellers.newService")} wide>
      <div className="space-y-3">
        <Input label={t("panel.botResellers.serviceName")} value={name} onChange={(e) => setName(e.target.value)} />
        <div>
          <p className="mb-1.5 text-sm text-muted">{t("panel.common.panel")}</p>
          <div className="flex flex-wrap gap-2">
            {panels.map((p) => (
              <button
                key={p.code}
                type="button"
                disabled={!!service}
                onClick={() => {
                  setPanelCode(p.code);
                  setGroupIds([]);
                }}
                className={`rounded-xl px-3 py-2 text-xs font-bold ring-1 ring-inset disabled:opacity-60 ${panelCode === p.code ? "bg-primary/15 text-primary ring-primary/40" : "ring-border"}`}
              >
                {p.name}
              </button>
            ))}
          </div>
        </div>
        <div>
          <p className="mb-1.5 text-sm text-muted">{t("panel.botResellers.groups")}</p>
          {groups.isError ? (
            <ErrorState message={groups.error.message} onRetry={() => void groups.refetch()} />
          ) : groups.isLoading ? (
            <Skeleton className="h-16 w-full rounded-xl" />
          ) : (
            <div className="flex flex-wrap gap-2">
              {groups.data?.groups.map((g) => (
                <button key={g.id} type="button" onClick={() => toggleGroup(g.id)} className={`rounded-xl px-3 py-2 text-xs font-bold ring-1 ring-inset ${groupIds.includes(g.id) ? "bg-primary/15 text-primary ring-primary/40" : "ring-border"}`}>
                  {groupIds.includes(g.id) ? "✓ " : ""}
                  {g.name}
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Input label={t("panel.botResellers.pricePerGb")} inputMode="numeric" ltr value={price} onChange={(e) => setPrice(e.target.value)} />
          <Input label={t("panel.botResellers.maxUsers")} inputMode="numeric" ltr value={maxUsers} onChange={(e) => setMaxUsers(e.target.value)} />
          <Input label={t("panel.botResellers.maxUserGb")} inputMode="decimal" ltr value={maxGb} onChange={(e) => setMaxGb(e.target.value)} />
          <Input label={t("panel.botResellers.maxUserDays")} inputMode="numeric" ltr value={maxDays} onChange={(e) => setMaxDays(e.target.value)} />
        </div>
        <p className="text-xs text-muted">{t("panel.botResellers.zeroUnlimited")}</p>
        <Input label={t("panel.botResellers.description")} value={description} onChange={(e) => setDescription(e.target.value)} />
        <Toggle on={onSale} onChange={setOnSale} label={t("panel.botResellers.showInBot")} />
        <Button
          fullWidth
          loading={save.isPending}
          disabled={!name.trim() || panelCode == null || !groupIds.length || num(price) == null}
          onClick={() =>
            save.mutate(
              {
                id: service?.id ?? null,
                panel_code: panelCode as number,
                name: name.trim(),
                description: description.trim() || null,
                group_ids: groupIds,
                price_per_gb: num(price) ?? 0,
                sale_enabled: onSale,
                max_users: num(maxUsers) ?? 0,
                max_user_gb: num(maxGb) ?? 0,
                max_user_days: num(maxDays) ?? 0,
              },
              { onSuccess: onClose }
            )
          }
        >
          {t("panel.botResellers.saveService")}
        </Button>
      </div>
    </Dialog>
  );
}
