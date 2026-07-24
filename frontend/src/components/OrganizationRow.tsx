/**
 * "Discover hidden gems" row on the Discover page -- per the plan's page
 * scope, organizations don't get a separate page/detail view this pass.
 */

import type { Organization } from "../api/types";
import { OrganizationCard } from "./OrganizationCard";

interface OrganizationRowProps {
  organizations: Organization[];
}

export function OrganizationRow({ organizations }: OrganizationRowProps) {
  if (organizations.length === 0) return null;

  return (
    <section className="organization-row">
      <h2>Discover hidden gems</h2>
      <div className="organization-row__scroll">
        {organizations.map((org) => (
          <OrganizationCard key={org.source_id} organization={org} />
        ))}
      </div>
    </section>
  );
}
