import type { Organization } from "../api/types";

interface OrganizationCardProps {
  organization: Organization;
}

export function OrganizationCard({ organization }: OrganizationCardProps) {
  return (
    <a
      className="organization-card"
      href={organization.url}
      target="_blank"
      rel="noreferrer"
    >
      <div
        className={`organization-card__image organization-card__image--${organization.category}`}
        style={
          organization.image_url ? { backgroundImage: `url(${organization.image_url})` } : undefined
        }
      >
        {!organization.image_url && <span>{organization.name.slice(0, 1)}</span>}
      </div>
      <div className="organization-card__name">{organization.name}</div>
      <div className="organization-card__meta">
        {organization.upcoming_event_count} upcoming event
        {organization.upcoming_event_count === 1 ? "" : "s"}
      </div>
    </a>
  );
}
