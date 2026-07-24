/**
 * Static, clearly-illustrative weather card -- not a live API call (no
 * external weather key added this pass, see plan's "Weather widget"
 * assumption). Explicitly labeled as illustrative so it can't be mistaken
 * for real data, consistent with the "never fabricate data" principle.
 */

const ILLUSTRATIVE_WEATHER = {
  condition: "Partly cloudy",
  high_f: 78,
  low_f: 64,
  is_live: false,
};

export function WeatherCard() {
  return (
    <div className="sidebar-card weather-card">
      <h3>Today in NYC</h3>
      <div className="weather-card__body">
        <span className="weather-card__condition">{ILLUSTRATIVE_WEATHER.condition}</span>
        <span className="weather-card__temps">
          {ILLUSTRATIVE_WEATHER.high_f}&deg; / {ILLUSTRATIVE_WEATHER.low_f}&deg;
        </span>
      </div>
      <p className="sidebar-card__disclaimer">Illustrative only, not a live forecast.</p>
    </div>
  );
}
