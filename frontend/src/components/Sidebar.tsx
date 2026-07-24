import type { HeroSearchValue } from "./HeroSearch";
import { PlanAtAGlance } from "./PlanAtAGlance";
import { PreferencesSummary } from "./PreferencesSummary";
import { WeatherCard } from "./WeatherCard";

interface SidebarProps {
  filters: HeroSearchValue;
  category?: string;
  resultCount: number;
  favoritesCount: number;
}

export function Sidebar({ filters, category, resultCount, favoritesCount }: SidebarProps) {
  return (
    <aside className="sidebar">
      <PlanAtAGlance filters={filters} category={category} resultCount={resultCount} />
      <WeatherCard />
      <PreferencesSummary favoritesCount={favoritesCount} />
    </aside>
  );
}
