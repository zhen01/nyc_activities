/**
 * Small sidebar widget summarizing this device's favorites count. Reads
 * from server-persisted favorites (via device_id), not localStorage.
 */

interface PreferencesSummaryProps {
  favoritesCount: number;
}

export function PreferencesSummary({ favoritesCount }: PreferencesSummaryProps) {
  return (
    <div className="sidebar-card preferences-summary">
      <h3>Your favorites</h3>
      <p>
        {favoritesCount === 0
          ? "Tap the heart on any activity to save it here."
          : `${favoritesCount} activit${favoritesCount === 1 ? "y" : "ies"} saved.`}
      </p>
    </div>
  );
}
