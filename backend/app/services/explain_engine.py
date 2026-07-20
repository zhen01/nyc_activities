"""
Generates the "why this fits, what's uncertain" text shown per
recommendation (product principle #4).

V1: rule-based templates built only from fields already verified in the
DB (no invented content — principle #2, "discovery without hallucination").
A future version may swap in an LLM call, but it must stay grounded to the
candidate's stored fields and cite the source/last_checked date.
"""

# TODO: implement template-based explanation generation.
