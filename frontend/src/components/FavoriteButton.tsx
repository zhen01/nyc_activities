/**
 * Heart toggle for one event. Optimistically flips local state, then
 * persists via POST/DELETE /favorites; reverts on failure. Server-side
 * persistence, not localStorage -- see api/client.ts's getOrCreateDeviceId.
 */

import { useState } from "react";

import { deleteFavorite, postFavorite } from "../api/client";

interface FavoriteButtonProps {
  deviceId: string;
  eventId: string;
  initialFavorited: boolean;
  onChange?: (favorited: boolean) => void;
}

export function FavoriteButton({ deviceId, eventId, initialFavorited, onChange }: FavoriteButtonProps) {
  const [favorited, setFavorited] = useState(initialFavorited);
  const [pending, setPending] = useState(false);

  async function toggle() {
    const next = !favorited;
    setFavorited(next);
    setPending(true);
    try {
      if (next) {
        await postFavorite(deviceId, eventId);
      } else {
        await deleteFavorite(deviceId, eventId);
      }
      onChange?.(next);
    } catch {
      setFavorited(!next);
    } finally {
      setPending(false);
    }
  }

  return (
    <button
      type="button"
      className={`favorite-button${favorited ? " favorite-button--active" : ""}`}
      onClick={toggle}
      disabled={pending}
      aria-pressed={favorited}
      aria-label={favorited ? "Remove from favorites" : "Add to favorites"}
    >
      {favorited ? "♥" : "♡"}
    </button>
  );
}
