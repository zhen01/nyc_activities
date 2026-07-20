# Maintaining the Source Directory

How to add or update an entry in `backend/data/sources.yaml`, and how to promote a
verified activity from a source into `backend/data/seed_activities.json`. This
directory is maintained manually by design (principle #6) — automation is deliberately
deferred until the curated data proves the product is useful.

## Adding a new source

1. Add an entry to `sources.yaml` with `name`, `category`, `channel_type`, `url`, and
   an `update_cadence` appropriate to how often that channel posts.
2. Leave `last_checked` as `null` until you've actually reviewed it.

## Promoting a source entry into a seed activity

1. Manually verify the activity is real, current, and matches the schema in
   `backend/app/db/models.py`.
2. Add an entry to `seed_activities.json` including a `source_url` and a `last_checked`
   date.
3. Re-run `python -m scripts.load_seed_data`.

## Re-check cadence

Revisit each source according to its `update_cadence` field, and update `last_checked`
every time you do — that date is what lets the app flag stale recommendations later.
