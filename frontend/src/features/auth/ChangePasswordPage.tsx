import { useState } from "react";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button, Card, Input } from "../../components/ui";
import { useToast } from "../../components/ui/Toast";
import { useChangePasswordMutation } from "../../queries/useAuth";

export default function ChangePasswordPage() {
  const changePassword = useChangePasswordMutation();
  const { show } = useToast();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      show("رمز عبور و تکرار آن یکسان نیست", "error");
      return;
    }
    try {
      const res = await changePassword.mutateAsync(password);
      show(res.message || "رمز عبور تغییر کرد", "success");
      setPassword("");
      setConfirm("");
    } catch (err) {
      show(err instanceof Error ? err.message : "خطا در تغییر رمز", "error");
    }
  }

  return (
    <div>
      <PageHeader title="تغییر رمز عبور" back="/profile" />
      <Card className="p-5">
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="رمز عبور جدید"
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
          <Button type="submit" fullWidth loading={changePassword.isPending}>
            ذخیره رمز جدید
          </Button>
        </form>
      </Card>
    </div>
  );
}
