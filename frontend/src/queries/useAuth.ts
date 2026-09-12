import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { authApi } from "../api/webapp";
import { useAuth } from "../context/AuthContext";
import { useWebAppAuth } from "../hooks/useWebAppAuth";

export function useProfileQuery() {
  const { auth, ready } = useWebAppAuth();

  return useQuery({
    queryKey: ["profile", auth?.session_token, auth?.init_data],
    queryFn: async () => {
      if (!auth?.init_data && !auth?.session_token) return null;
      if (auth.init_data) {
        const res = await authApi.getInfoWithInitData(auth.init_data);
        return res.user ?? null;
      }
      const res = await authApi.getInfoSession(auth.session_token!);
      return res.user ?? null;
    },
    enabled: ready,
  });
}

export function useRegistrationStatusQuery() {
  return useQuery({
    queryKey: ["registration-status"],
    queryFn: () => authApi.getRegistrationStatus(),
  });
}

export function useCreateAccountMutation() {
  const { sessionToken, refreshUser } = useAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: { username: string; password: string }) =>
      authApi.createAccount({ ...body, session_token: sessionToken }),
    onSuccess: async () => {
      await refreshUser();
      await queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
  });
}

export function useChangePasswordMutation() {
  const { sessionToken } = useAuth();

  return useMutation({
    mutationFn: (newPassword: string) =>
      authApi.changePassword({ new_password: newPassword, session_token: sessionToken }),
  });
}
