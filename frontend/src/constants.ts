/**
 * Mirrors backend/app/services/presentation.py's CATEGORY_LABELS and the
 * 7-category taxonomy in data/sample/events.csv. `food_drink` and `learn`
 * currently have zero seed rows (see STATUS.md) -- they still appear here
 * so the filter row's shape matches the full taxonomy, but selecting them
 * is expected to return an empty result set until sample data exists.
 */
export const CATEGORIES: { value: string; label: string }[] = [
  { value: "active", label: "Active" },
  { value: "outdoors", label: "Outdoors" },
  { value: "social", label: "Social" },
  { value: "culture", label: "Culture" },
  { value: "food_drink", label: "Food & Drink" },
  { value: "learn", label: "Learn" },
  { value: "volunteer", label: "Volunteer" },
];

export const HOURS_FREE_OPTIONS: { value: number; label: string }[] = [
  { value: 1, label: "1 hour" },
  { value: 2, label: "2 hours" },
  { value: 3, label: "3 hours" },
  { value: 5, label: "5 hours" },
  { value: 8, label: "All day" },
];

export const INTENT_OPTIONS: { value: string; label: string }[] = [
  { value: "meet_people", label: "Meet people" },
  { value: "solo_time", label: "Solo time" },
  { value: "explore", label: "Explore" },
];
