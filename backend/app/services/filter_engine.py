"""
Feasibility filtering — product principle #1: "feasibility before
attractiveness".

Given UserConstraints, queries the DB for activities that actually fit
(time window overlap, budget ceiling, travel-time/location radius,
solo-friendly flag, skill level) BEFORE any ranking by how appealing an
activity is. Returns a small candidate set, not a full catalog.
"""

# TODO: implement DB query + hard-constraint filtering logic.
