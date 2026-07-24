/**
 * Renders one Recommendation as a photo card: image (or a category-colored
 * placeholder when image_url is absent -- never fabricated/hotlinked, see
 * plan's "Images" assumption), badges/tags, a meta row, the "why this
 * fits" explanation, and a confidence label. Uncertainty is shown, not
 * hidden -- principle #4.
 */

import type { Recommendation } from "../api/types";
import { FavoriteButton } from "./FavoriteButton";

interface ActivityCardProps {
  activity: Recommendation;
  deviceId: string;
  onFavoriteChange?: (favorited: boolean) => void;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatCost(cost: number | null): string {
  if (cost === null) return "Cost unknown";
  if (cost === 0) return "Free";
  return `$${cost.toFixed(0)}`;
}

export function ActivityCard({ activity, deviceId, onFavoriteChange }: ActivityCardProps) {
  return (
    <article className="activity-card">
      <div
        className={`activity-card__image activity-card__image--${activity.category}`}
        style={activity.image_url ? { backgroundImage: `url(${activity.image_url})` } : undefined}
      >
        {!activity.image_url && <span>{activity.category_label}</span>}
        <FavoriteButton
          deviceId={deviceId}
          eventId={activity.event_id}
          initialFavorited={activity.is_favorited ?? false}
          onChange={onFavoriteChange}
        />
      </div>

      <div className="activity-card__body">
        <div className="activity-card__badges">
          {activity.badges.map((badge) => (
            <span key={badge} className="badge">
              {badge}
            </span>
          ))}
        </div>

        <h3 className="activity-card__title">{activity.title}</h3>

        <div className="activity-card__meta">
          <span>{formatTime(activity.start_time)}</span>
          <span>{formatCost(activity.cost)}</span>
          {activity.duration_minutes !== null && <span>{activity.duration_minutes} min</span>}
          {activity.estimated_transit_minutes !== null && (
            <span>~{activity.estimated_transit_minutes} min by subway</span>
          )}
        </div>

        <p className="activity-card__location">{activity.location}</p>

        {activity.tags.length > 0 && (
          <div className="activity-card__tags">
            {activity.tags.map((tag) => (
              <span key={tag} className="tag">
                {tag}
              </span>
            ))}
          </div>
        )}

        <p className="activity-card__explanation">{activity.explanation}</p>

        <div className={`confidence confidence--${activity.confidence_label.toLowerCase()}`}>
          {activity.confidence_label} confidence &middot; via {activity.source_name}
        </div>
      </div>
    </article>
  );
}
