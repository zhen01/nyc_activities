/**
 * Thin fetch wrapper for the backend. Relative paths only -- in dev,
 * vite.config.ts proxies them to localhost:8000; in "prod" the built app
 * is served from the same FastAPI origin (see backend/app/main.py), so no
 * base URL configuration is needed.
 */

import type { Organization, Recommendation, UserConstraints } from "./types";

const DEVICE_ID_KEY = "nyc-activities:device-id";

/**
 * Anonymous, client-generated UUID used only to scope favorites to this
 * browser -- there is no login/auth system (see UserConstraints.device_id
 * in backend/app/models/schema.py). Persisted in localStorage so favorites
 * survive a page reload.
 */
export function getOrCreateDeviceId(): string {
  const existing = localStorage.getItem(DEVICE_ID_KEY);
  if (existing) return existing;
  const created = crypto.randomUUID();
  localStorage.setItem(DEVICE_ID_KEY, created);
  return created;
}

async function handle<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    throw new Error(`${resp.status} ${resp.statusText}: ${await resp.text()}`);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}

export async function getRecommendations(
  constraints: UserConstraints,
): Promise<Recommendation[]> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(constraints)) {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  }
  const resp = await fetch(`/recommendations?${params.toString()}`);
  return handle<Recommendation[]>(resp);
}

export async function getOrganizations(): Promise<Organization[]> {
  const resp = await fetch("/organizations");
  return handle<Organization[]>(resp);
}

export async function getFavorites(deviceId: string): Promise<string[]> {
  const params = new URLSearchParams({ device_id: deviceId });
  const resp = await fetch(`/favorites?${params.toString()}`);
  return handle<string[]>(resp);
}

export async function postFavorite(deviceId: string, eventId: string): Promise<void> {
  const resp = await fetch("/favorites", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ device_id: deviceId, event_id: eventId }),
  });
  return handle<void>(resp);
}

export async function deleteFavorite(deviceId: string, eventId: string): Promise<void> {
  const resp = await fetch(
    `/favorites/${encodeURIComponent(deviceId)}/${encodeURIComponent(eventId)}`,
    { method: "DELETE" },
  );
  return handle<void>(resp);
}
