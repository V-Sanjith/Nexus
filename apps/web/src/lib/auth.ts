export interface SessionUser {
  id: string;
  email: string;
  name?: string;
}

export function getSessionUser(): SessionUser | null {
  if (typeof window === "undefined") return null;
  
  const userData = localStorage.getItem("nexus_user");
  if (!userData) return null;
  
  try {
    return JSON.parse(userData) as SessionUser;
  } catch {
    return null;
  }
}
