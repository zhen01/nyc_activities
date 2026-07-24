/**
 * Root component for the Discover page. Holds search/category state,
 * calls the backend via api/client.ts, and renders the activity grid,
 * organizations row, and sidebar widgets. No routing/state library --
 * one screen, consistent with the project's existing principle.
 */

import { useEffect, useState } from "react";

import { getFavorites, getOrCreateDeviceId, getOrganizations, getRecommendations } from "./api/client";
import type { Organization, Recommendation } from "./api/types";
import { ActivityCard } from "./components/ActivityCard";
import { CategoryFilterRow } from "./components/CategoryFilterRow";
import { HeroSearch, type HeroSearchValue } from "./components/HeroSearch";
import { OrganizationRow } from "./components/OrganizationRow";
import { Sidebar } from "./components/Sidebar";
import { TopNav } from "./components/TopNav";

const deviceId = getOrCreateDeviceId();

export default function App() {
  const [filters, setFilters] = useState<HeroSearchValue>({});
  const [category, setCategory] = useState<string | undefined>(undefined);
  const [activities, setActivities] = useState<Recommendation[]>([]);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [favoritesCount, setFavoritesCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function runSearch(nextFilters: HeroSearchValue, nextCategory: string | undefined) {
    setLoading(true);
    setError(null);
    try {
      const results = await getRecommendations({
        category: nextCategory,
        hours_free: nextFilters.hoursFree,
        date: nextFilters.date,
        after_time: nextFilters.afterTime,
        intent: nextFilters.intent,
        device_id: deviceId,
      });
      setActivities(results);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong loading activities.");
    } finally {
      setLoading(false);
    }
  }

  async function refreshFavoritesCount() {
    try {
      const favorites = await getFavorites(deviceId);
      setFavoritesCount(favorites.length);
    } catch {
      // Favorites are a nice-to-have widget; a failed count fetch
      // shouldn't block the rest of the page.
    }
  }

  useEffect(() => {
    void runSearch(filters, category);
    void refreshFavoritesCount();
    getOrganizations()
      .then(setOrganizations)
      .catch(() => setOrganizations([]));
    // Only re-run on mount; category/filter changes call runSearch directly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleSearch(nextFilters: HeroSearchValue) {
    setFilters(nextFilters);
    void runSearch(nextFilters, category);
  }

  function handleCategorySelect(nextCategory: string | undefined) {
    setCategory(nextCategory);
    void runSearch(filters, nextCategory);
  }

  return (
    <div className="app">
      <TopNav favoritesCount={favoritesCount} />
      <HeroSearch onSearch={handleSearch} />
      <CategoryFilterRow selected={category} onSelect={handleCategorySelect} />

      <div className="app__content">
        <main className="app__main">
          {error && <p className="app__error">{error}</p>}
          {!error && loading && <p className="app__status">Loading activities...</p>}
          {!error && !loading && activities.length === 0 && (
            <p className="app__status">
              No activities match these filters right now -- try widening your search.
            </p>
          )}
          <div className="activity-grid">
            {activities.map((activity) => (
              <ActivityCard
                key={activity.event_id}
                activity={activity}
                deviceId={deviceId}
                onFavoriteChange={() => void refreshFavoritesCount()}
              />
            ))}
          </div>
          <OrganizationRow organizations={organizations} />
        </main>

        <Sidebar
          filters={filters}
          category={category}
          resultCount={activities.length}
          favoritesCount={favoritesCount}
        />
      </div>
    </div>
  );
}
