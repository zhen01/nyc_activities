/**
 * Mirrors backend/app/models/schema.py. Kept as plain interfaces (no
 * runtime validation library) -- the backend is the source of truth for
 * these shapes; this file exists so the frontend gets type-checking, not
 * as an independent schema.
 */

export type Mode = "specific" | "mood" | "surprise";
export type Intent = "meet_people" | "solo_time" | "explore";

export interface UserConstraints {
  category?: string;
  max_cost?: number;
  solo_friendly?: boolean;
  date?: string;
  zip_code?: string;
  mode?: Mode;
  vibe?: string;
  hours_free?: number;
  intent?: Intent;
  after_time?: string;
  device_id?: string;
}

export interface Recommendation {
  event_id: string;
  title: string;
  category: string;
  start_time: string;
  end_time: string | null;
  cost: number | null;
  location: string;
  solo_friendly: boolean;
  source_url: string | null;
  source_name: string;
  source_verified_date: string;
  distance_miles: number | null;
  confidence_label: string;
  confidence_score: number;
  score: number;
  explanation: string;
  image_url: string | null;
  category_label: string;
  badges: string[];
  tags: string[];
  estimated_transit_minutes: number | null;
  duration_minutes: number | null;
  is_favorited: boolean | null;
}

export interface Organization {
  source_id: string;
  name: string;
  category: string;
  channel_type: string;
  url: string;
  image_url: string | null;
  upcoming_event_count: number;
}
