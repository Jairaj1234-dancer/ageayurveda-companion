const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function apiFetch<T>(
  path: string,
  token: string,
  opts?: RequestInit
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...opts?.headers,
    },
  });
  if (res.status === 401) throw new Error("unauthorized");
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
