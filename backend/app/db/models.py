"""
SQLAlchemy ORM models: Organization, Activity, Source.

Organization: a small org/community from sources.yaml once curated.
Activity: one concrete, verified, attendable activity tied to an
    Organization (time, cost, location, solo-friendly flag, source URL,
    last_checked date).
Source: the origin channel for an Activity, used to show provenance and
    flag staleness in the UI.
"""

# TODO: define ORM classes + relationships.
