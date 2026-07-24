/**
 * Summarizes the currently-active search: only echoes constraints the
 * user actually set (never fabricates a "plan" beyond what was asked).
 */

import { CATEGORIES, HOURS_FREE_OPTIONS, INTENT_OPTIONS } from "../constants";
import type { HeroSearchValue } from "./HeroSearch";

interface PlanAtAGlanceProps {
  filters: HeroSearchValue;
  category?: string;
  resultCount: number;
}

export function PlanAtAGlance({ filters, category, resultCount }: PlanAtAGlanceProps) {
  const hoursLabel = HOURS_FREE_OPTIONS.find((o) => o.value === filters.hoursFree)?.label;
  const intentLabel = INTENT_OPTIONS.find((o) => o.value === filters.intent)?.label;
  const categoryLabel = CATEGORIES.find((c) => c.value === category)?.label;

  const rows = [
    hoursLabel && ["Free time", hoursLabel],
    filters.date && ["Date", filters.date],
    filters.afterTime && ["After", filters.afterTime],
    intentLabel && ["Looking to", intentLabel],
    categoryLabel && ["Category", categoryLabel],
  ].filter(Boolean) as [string, string][];

  return (
    <div className="sidebar-card plan-at-a-glance">
      <h3>Plan at a glance</h3>
      {rows.length === 0 ? (
        <p className="sidebar-card__disclaimer">No filters set -- showing top picks.</p>
      ) : (
        <dl>
          {rows.map(([label, value]) => (
            <div key={label} className="plan-at-a-glance__row">
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      )}
      <p className="plan-at-a-glance__count">
        {resultCount} match{resultCount === 1 ? "" : "es"}
      </p>
    </div>
  );
}
