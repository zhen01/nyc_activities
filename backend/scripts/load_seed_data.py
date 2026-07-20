"""
One-time/repeatable loader: reads backend/data/seed_activities.json and
upserts rows into the Activity/Organization tables via app.db.models.

This is the only way data enters the database in the MVP -- no live
scraping, no automated ingestion (principle #5: progressive engineering,
principle #6: human-maintainable sources).

Run with: python -m scripts.load_seed_data
"""

# TODO: implement JSON -> ORM upsert logic.
