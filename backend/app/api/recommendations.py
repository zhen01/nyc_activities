"""
POST /recommendations

Accepts a user's time/budget/location/solo constraints, runs them through
filter_engine (feasibility) and explain_engine (why-it-fits copy), and
returns a small (1-3 item) list of Recommendation objects.

This is the only HTTP endpoint the frontend talks to in the MVP.
"""

# TODO: define an APIRouter, parse UserConstraints from the request body,
# call filter_engine then explain_engine, return list[Recommendation].
