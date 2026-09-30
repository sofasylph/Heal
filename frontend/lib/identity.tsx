"use client";

import { createContext, useContext, useEffect, useState } from "react";

export type Role = "reviewer" | "senior_reviewer" | "auditor";

export interface Identity {
  user: string;
  role: Role;
}

export const ROLES: { id: Role; label: string; description: string }[] = [
  { id: "reviewer", label: "Reviewer", description: "Submits claims; decides auto-candidate and verify claims." },
  { id: "senior_reviewer", label: "Senior reviewer", description: "Also decides escalated claims and changes model settings." },
  { id: "auditor", label: "Auditor", description: "Read-only: claims, audit trails, analytics." },
];

const KEY = "claimtrace.identity";
const DEFAULT: Identity = { user: "demo.reviewer", role: "reviewer" };

// Module-level copy so the API client can attach headers without React context.
let current: Identity = DEFAULT;
export const getIdentity = () => current;

function load(): Identity {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const v = JSON.parse(raw) as Identity;
      if (v.user && ROLES.some((r) => r.id === v.role)) return v;
    }
  } catch {
    /* storage unavailable: fall back to default */
  }
  return DEFAULT;
}

const Ctx = createContext<{ identity: Identity; setIdentity: (i: Identity) => void }>({
  identity: DEFAULT,
  setIdentity: () => {},
});

export function IdentityProvider({ children }: { children: React.ReactNode }) {
  const [identity, setState] = useState<Identity>(DEFAULT);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const i = load();
    current = i;
    setState(i);
    setReady(true);
  }, []);

  const setIdentity = (i: Identity) => {
    current = i;
    setState(i);
    try {
      localStorage.setItem(KEY, JSON.stringify(i));
    } catch {
      /* ignore */
    }
  };

  // Children render only after the stored identity is loaded, so first requests carry it.
  return <Ctx.Provider value={{ identity, setIdentity }}>{ready ? children : null}</Ctx.Provider>;
}

export const useIdentity = () => useContext(Ctx);

export const can = {
  submit: (r: Role) => r !== "auditor",
  decide: (r: Role, route: string | null | undefined) =>
    r === "senior_reviewer" || (r === "reviewer" && route !== "escalate"),
  settings: (r: Role) => r === "senior_reviewer",
};
