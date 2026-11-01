import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { getHealth, type Health } from "./api";
import { setProviderName } from "./i18n";

interface HealthState { health: Health | null; reachable: boolean | null; recheck: () => void }
const Ctx = createContext<HealthState>({ health: null, reachable: null, recheck: () => {} });

export function HealthProvider({ children }: { children: React.ReactNode }) {
  const [health, setHealth] = useState<Health | null>(null);
  const [reachable, setReachable] = useState<boolean | null>(null);
  const recheck = useCallback(() => {
    getHealth()
      .then((h) => {
        setHealth(h);
        setProviderName(h.llm_provider === "claude_cli" ? "Claude" : "Gemini");
        setReachable(true);
      })
      .catch(() => setReachable(false));
  }, []);
  useEffect(() => {
    recheck();
    const id = window.setInterval(recheck, 45000);
    const on = () => recheck();
    window.addEventListener("online", on);
    return () => {
      window.clearInterval(id);
      window.removeEventListener("online", on);
    };
  }, [recheck]);
  return <Ctx.Provider value={{ health, reachable, recheck }}>{children}</Ctx.Provider>;
}

export const useHealth = () => useContext(Ctx);
