"""Central settings for the MarsWalk processing scripts.

The area values below are placeholders until a real NASA data footprint is
selected. They must not be presented as measured mission data.
"""

import math
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
DEM_PATH = PROCESSED_DATA_DIR / "dem.tif"
SLOPE_PATH = PROCESSED_DATA_DIR / "slope.tif"
HAZARD_PATH = PROCESSED_DATA_DIR / "hazard.tif"
ROUTE_PATH = PROCESSED_DATA_DIR / "route.geojson"
STATS_PATH = PROCESSED_DATA_DIR / "stats.json"
GRID_PATH = PROCESSED_DATA_DIR / "grid.json"

MARS_RADIUS_KM = 3389.5
KM_PER_DEG = 2 * math.pi * MARS_RADIUS_KM / 360

# PLACEHOLDER AOI: replace with bounds from the selected NASA data footprint.
CENTER_LAT = -4.64173
CENTER_LON = 137.66
HALF_SIDE_KM = 2.5

dlat = HALF_SIDE_KM / KM_PER_DEG
dlon = HALF_SIDE_KM / (KM_PER_DEG * math.cos(math.radians(CENTER_LAT)))

# PLACEHOLDER AOI bounds, derived from the placeholder center and size above.
AOI_BOUNDS = {
    "min_lat": CENTER_LAT - dlat,
    "max_lat": CENTER_LAT + dlat,
    "min_lon": CENTER_LON - dlon,
    "max_lon": CENTER_LON + dlon,
}

# PLACEHOLDER mission points in (row, column) raster pixels.
HABITAT_PIXEL = (32, 6)
SCIENCE_TARGET_PIXELS = ((16, 24), (42, 42), (30, 55))

# ASSUMPTION: maximum slope considered walkable by a suited astronaut.
MAX_WALKABLE_SLOPE_DEG = 15.0
# ASSUMPTION: average walking speed for a suited astronaut.
WALKING_SPEED_KMH = 3.0
# ASSUMPTION: planned maximum EVA duration before return.
EVA_HOURS = 4.0
# ASSUMPTION: estimated radiation dose rate used for planning displays.
DOSE_RATE_MSV_PER_HOUR = 0.02
# ROUTE SETTING: emphasize steeper cells while keeping the route within the
# configured EVA time limit.
SLOPE_COST_POWER = 1.1