/**
 * Category chips. Selecting one sets a hard category filter (mode
 * "specific" in UserConstraints); "All" clears it. Mirrors the 7-category
 * taxonomy in constants.ts.
 */

import { CATEGORIES } from "../constants";

interface CategoryFilterRowProps {
  selected?: string;
  onSelect: (category: string | undefined) => void;
}

export function CategoryFilterRow({ selected, onSelect }: CategoryFilterRowProps) {
  return (
    <div className="category-filter-row">
      <button
        type="button"
        className={`category-chip${!selected ? " category-chip--active" : ""}`}
        onClick={() => onSelect(undefined)}
      >
        All
      </button>
      {CATEGORIES.map((cat) => (
        <button
          key={cat.value}
          type="button"
          className={`category-chip${selected === cat.value ? " category-chip--active" : ""}`}
          onClick={() => onSelect(cat.value)}
        >
          {cat.label}
        </button>
      ))}
    </div>
  );
}
