import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Button, ErrorState, Input, Skeleton } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";
import { panelPwaApi } from "../../api/panel";
import { useWebAppAuth } from "../../hooks/useWebAppAuth";
import { usePanelAction, usePanelQuery } from "../../queries/usePanelApi";
import { applyPwaBranding } from "../../pwaBranding";
import { SectionCard } from "./components";

const ACCEPTED_TYPES = "image/png,image/jpeg,image/webp,image/gif,image/bmp";

export function PwaSettingsSection() {
  const { t } = useTranslation();
  const { auth } = useWebAppAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const query = usePanelQuery(["pwa"], (a) => panelPwaApi.getPwaSettings(a));
  const save = usePanelAction(panelPwaApi.savePwaSettings, { invalidate: [["pwa"]] });

  const [appName, setAppName] = useState("");
  const [shortName, setShortName] = useState("");
  const [description, setDescription] = useState("");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!query.data || loaded) return;
    setAppName(query.data.app_name);
    setShortName(query.data.short_name);
    setDescription(query.data.description);
    setLoaded(true);
  }, [query.data, loaded]);

  const upload = useMutation({
    mutationFn: (file: File) => panelPwaApi.uploadPwaIcon(file, auth || {}),
    onSuccess: (result) => {
      toast.show(result.message || t("panel.pwa.iconUpdated"), "success");
      void queryClient.invalidateQueries({ queryKey: ["panel", "pwa"] });
      void applyPwaBranding();
    },
    onError: (error: Error) => toast.show(error.message || "عملیات انجام نشد", "error"),
  });

  if (query.isError) {
    return <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />;
  }
  if (query.isLoading || !query.data) {
    return <Skeleton className="h-64 w-full" />;
  }

  const iconUrl = `/api/webapp/icons/icon-192.png?v=${query.data.icon_version}`;

  function handleFilePick(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (file) upload.mutate(file);
  }

  return (
    <SectionCard
      title={t("panel.pwa.title")}
      description={t("panel.pwa.subtitle")}
      actions={
        <Button
          size="sm"
          loading={save.isPending}
          onClick={() =>
            save.mutate(
              { app_name: appName, short_name: shortName, description },
              { onSuccess: () => void applyPwaBranding() }
            )
          }
        >
          {t("panel.settings.saveSection")}
        </Button>
      }
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
        <div className="flex flex-col items-center gap-2">
          <img
            key={iconUrl}
            src={iconUrl}
            alt={t("panel.pwa.iconAlt")}
            className="h-20 w-20 rounded-2xl object-cover ring-1 ring-border"
          />
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_TYPES}
            className="hidden"
            onChange={handleFilePick}
          />
          <Button
            size="sm"
            variant="secondary"
            loading={upload.isPending}
            onClick={() => fileInputRef.current?.click()}
          >
            {t("panel.pwa.uploadIcon")}
          </Button>
        </div>

        <div className="grid flex-1 gap-3 sm:grid-cols-2">
          <Input
            label={t("panel.pwa.appName")}
            value={appName}
            maxLength={45}
            onChange={(event) => setAppName(event.target.value)}
          />
          <Input
            label={t("panel.pwa.shortName")}
            value={shortName}
            maxLength={12}
            onChange={(event) => setShortName(event.target.value)}
          />
          <label className="block w-full text-sm sm:col-span-2">
            <span className="mb-1.5 block text-muted">{t("panel.pwa.description")}</span>
            <textarea
              value={description}
              maxLength={300}
              rows={2}
              onChange={(event) => setDescription(event.target.value)}
              className="w-full resize-none rounded-md border border-border bg-surface px-3 py-2 text-sm text-text outline-none transition-[border-color,box-shadow] duration-200 placeholder:text-muted focus:border-primary focus:ring-4 focus:ring-primary/10"
            />
          </label>
        </div>
      </div>

      <p className="mt-4 border-t border-border pt-3 text-xs text-muted">{t("panel.pwa.hint")}</p>
    </SectionCard>
  );
}
