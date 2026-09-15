import { useQuery } from "@tanstack/react-query";
import { authApi } from "../api/webapp";
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
