import { useMemo } from "react";
import { useAuth } from "../context/AuthContext";

/** Stable auth payload for API calls — avoids useEffect loops from new object refs each render. */
export function useWebAppAuth() {
  const { sessionToken, initData } = useAuth();

  const auth = useMemo(() => {
    if (sessionToken != null) return { session_token: sessionToken };
    if (initData != null) return { init_data: initData };
    return null;
  }, [sessionToken, initData]);

  return { auth, sessionToken, initData, ready: auth != null };
}
