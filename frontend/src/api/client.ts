export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    let message = "";
    try {
      const data = await res.json();
      if (typeof data?.detail === "string") message = data.detail;
      else if (data?.detail) message = JSON.stringify(data.detail);
    } catch {
      message = await res.text().catch(() => "");
    }
    throw new Error(message || res.statusText || `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}
