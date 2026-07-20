"""
FastAPI application entrypoint.

Wires together the API routers (currently just /recommendations) and
app-level startup concerns (DB connection, CORS for the frontend).

Run with: uvicorn app.main:app --reload
"""

# TODO: create FastAPI() app, include the recommendations router,
# configure CORS using app.config.Settings.ALLOWED_ORIGINS.
