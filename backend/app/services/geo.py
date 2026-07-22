"""ZIP-code proximity support.

No geocoding API in scope -- we ship a small, human-maintainable NYC ZIP
centroid table (data/sample/zip_centroids.csv) and compute straight-line
("as the crow flies") distance. This is approximate by design: good enough
to rank "nearby" vs. "far", not meant to be routing-accurate.
"""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from typing import Optional

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
ZIP_CENTROIDS_CSV = REPO_ROOT / "data" / "sample" / "zip_centroids.csv"

EARTH_RADIUS_MILES = 3958.8

_zip_lookup: Optional[pd.DataFrame] = None


def _load_zip_centroids() -> pd.DataFrame:
    global _zip_lookup
    if _zip_lookup is None:
        df = pd.read_csv(ZIP_CENTROIDS_CSV, dtype={"zip_code": str})
        _zip_lookup = df.set_index("zip_code")
    return _zip_lookup


def zip_to_latlon(zip_code: str) -> Optional[tuple[float, float]]:
    """Look up a ZIP code's centroid. Returns None for unknown ZIPs --
    callers should treat that as "can't compute distance", not an error,
    since the lookup table is a small curated sample, not exhaustive.
    """
    lookup = _load_zip_centroids()
    zip_code = str(zip_code).strip()
    if zip_code not in lookup.index:
        return None
    row = lookup.loc[zip_code]
    return float(row["lat"]), float(row["lon"])


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line distance between two lat/lon points, in miles."""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * asin(sqrt(a))
