import { useState } from "react";
import { Navigate } from "react-router-dom";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button, Card, Input } from "../../components/ui";
import { ErrorState } from "../../components/ui/EmptyState";
import { Skeleton } from "../../components/ui/Skeleton";
import { useToast } from "../../components/ui/Toast";
import { useCreateAccountMutation, useRegistrationStatusQuery } from "../../queries/useAuth";

export default function AccountCreatePage() {
  const { data: status, isLoading, isError, refetch } = useRegistrationStatusQuery();
  const createAccount = useCreateAccountMutation();
  const { show } = useToast();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");

  if (isLoading) {
    return (
      <div>
        <PageHeader title="ساخت اکانت وب" back="/profile" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (isError || !status?.ok) {
    return (
      <div>
        <PageHeader title="ساخت اکانت وب" back="/profile" />
        <ErrorState message="خطا در بارگذاری وضعیت ثبت‌نام" onRetry={() => void refetch()} />
      </div>
    );
  }

  const registrationOpen = status.message !== "closed";

  if (!registrationOpen) {
    return <Navigate to="/profile" replace />;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      show("رمز عبور و تکرار آن یکسان نیست", "error");
      return;
    }
    try {
      const res = await createAccount.mutateAsync({ username: username.trim(), password });
      show(res.message || "اکانت با موفقیت ساخته شد", "success");
      setUsername("");
      setPassword("");
      setConfirm("");
    } catch (err) {
      show(err instanceof Error ? err.message : "خطا در ساخت اکانت", "error");
    }
  }

  return (
    <div>
      <PageHeader title="ساخت اکانت وب" subtitle={status.message} back="/profile" />
      <Card className="p-5">
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="نام کاربری"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            minLength={3}
          />
          <Input
            label="رمز عبور"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={6}
          />
          <Input
            label="تکرار رمز عبور"
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
            minLength={6}
          />
          <Button type="submit" fullWidth loading={createAccount.isPending}>
            ساخت اکانت
          </Button>
        </form>
      </Card>
    </div>
  );
}
