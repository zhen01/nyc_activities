/**
 * The hero search bar: three dropdowns (hours free, date + after-time,
 * intent) mapped 1:1 onto UserConstraints' hero-search fields (see
 * backend/app/models/schema.py). Category is a separate control
 * (CategoryFilterRow), not part of this bar.
 */

import { useState, type FormEvent } from "react";

import { HOURS_FREE_OPTIONS, INTENT_OPTIONS } from "../constants";
import type { Intent } from "../api/types";

export interface HeroSearchValue {
  hoursFree?: number;
  date?: string;
  afterTime?: string;
  intent?: Intent;
}

interface HeroSearchProps {
  onSearch: (value: HeroSearchValue) => void;
}

export function HeroSearch({ onSearch }: HeroSearchProps) {
  const [hoursFree, setHoursFree] = useState<string>("");
  const [date, setDate] = useState<string>("");
  const [afterTime, setAfterTime] = useState<string>("");
  const [intent, setIntent] = useState<string>("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    onSearch({
      hoursFree: hoursFree ? Number(hoursFree) : undefined,
      date: date || undefined,
      afterTime: afterTime || undefined,
      intent: (intent || undefined) as Intent | undefined,
    });
  }

  return (
    <form className="hero-search" onSubmit={handleSubmit}>
      <h1 className="hero-search__title">What are you free to do in NYC?</h1>
      <div className="hero-search__row">
        <label className="hero-search__field">
          <span>Free time</span>
          <select value={hoursFree} onChange={(e) => setHoursFree(e.target.value)}>
            <option value="">Any</option>
            {HOURS_FREE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>

        <label className="hero-search__field">
          <span>Date</span>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>

        <label className="hero-search__field">
          <span>After</span>
          <input type="time" value={afterTime} onChange={(e) => setAfterTime(e.target.value)} />
        </label>

        <label className="hero-search__field">
          <span>Looking to</span>
          <select value={intent} onChange={(e) => setIntent(e.target.value)}>
            <option value="">Any</option>
            {INTENT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>

        <button type="submit" className="hero-search__submit">
          Search
        </button>
      </div>
    </form>
  );
}
