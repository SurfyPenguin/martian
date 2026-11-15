"""Site configuration and adjustable EVA assumptions."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
MARS_RADIUS_M = 3_389_500.0

SITES = {
    "site1": {
        "name": "Gale crater floor",
        "provenance": (
            "NASA-provided clipped DEM and CTX input; product ID and acquisition "
            "date were not supplied."
        ),
        "dem_path": PROCESSED_DATA_DIR / "site1_dem.tif",
        "imagery_path": PROCESSED_DATA_DIR / "site1_imagery.tif",
        "bounds": {
            "min_lon": 137.38372932,
            "min_lat": -4.62945782,
            "max_lon": 137.46856732,
            "max_lat": -4.54495782,
        },
        # PLACEHOLDER coordinates: replace with mission-provided points.
        "habitat": {"lat": -4.58720782, "lon": 137.42614832},
        # PLACEHOLDER coordinates: replace with mission-provided science targets.
        "targets": [
            {"lat": -4.57420782, "lon": 137.40714832},
            {"lat": -4.60820782, "lon": 137.44714832},
            {"lat": -4.56520782, "lon": 137.45614832},
        ],
    },
    "site2": {
        "name": "Southern box",
        "provenance": (
            "NASA-provided clipped DEM and CTX input; product ID and acquisition "
            "date were not supplied."
        ),
        "dem_path": PROCESSED_DATA_DIR / "site2_dem.tif",
        "imagery_path": PROCESSED_DATA_DIR / "site2_imagery.tif",
        "bounds": {
            "min_lon": 137.35759675,
            "min_lat": -4.84236515,
            "max_lon": 137.44243475,
            "max_lat": -4.75769615,
        },
        # PLACEHOLDER coordinates: replace with mission-provided points.
        "habitat": {"lat": -4.80206271, "lon": 137.40721259},
        # PLACEHOLDER coordinates: replace with mission-provided science targets.
        "targets": [
            {"lat": -4.80511079, "lon": 137.41517144},
            {"lat": -4.80172403, "lon": 137.41686481},
            {"lat": -4.79495051, "lon": 137.41347807},
        ],
    },
}

# ASSUMPTION: maximum slope considered walkable by a suited astronaut.
MAX_WALKABLE_SLOPE_DEG = 15.0
# ASSUMPTION: local 5x5 elevation standard deviation above this value is
# considered too rough for the planned EVA.
MAX_ROUGHNESS_M = 15.0
# ASSUMPTION: keep this many cells clear between a route and any hazard.
SAFETY_MARGIN_CELLS = 2
# ROUTE SETTING: start tapering a soft hazard-clearance penalty at this radius.
CLEARANCE_COST_RADIUS_CELLS = 6.0
# ROUTE SETTING: maximum added traversal cost at the clearance radius.
CLEARANCE_COST_WEIGHT = 0.5
# ROUTE SETTING: extra clearance cost used by the optional Safer route.
SAFER_CLEARANCE_COST_WEIGHT = 2.5
# ROUTE SETTING: default heuristic weight for Weighted A*.
WEIGHTED_ASTAR_EPSILON = 1.5
# ROUTE SETTINGS: parameters for the optional Alternate path search.
ALTERNATE_ROUTE_COST_MULTIPLIER = 3.0
ALTERNATE_ROUTE_CORRIDOR_CELLS = 15
ALTERNATE_ROUTE_MIN_LEG_CELLS = 40
ALTERNATE_ROUTE_MAX_OVERLAP = 0.6
ALTERNATE_ROUTE_MAX_TIME_FACTOR = 1.4
# ASSUMPTION: average walking speed for a suited astronaut.
WALKING_SPEED_KMH = 3.0
# ASSUMPTION: planned maximum EVA duration before return.
EVA_HOURS = 4.0
# ASSUMPTION: estimated radiation dose rate used for planning displays.
DOSE_RATE_MSV_PER_HOUR = 0.02
# ROUTE SETTING: weight slope and roughness while preferring shorter paths.
SLOPE_COST_POWER = 1.0
ROUGHNESS_COST_WEIGHT = 0.05


def site_config(site: str) -> dict:
    try:
        return SITES[site]
    except KeyError as error:
        choices = ", ".join(SITES)
        raise ValueError(f"Unknown site {site!r}; choose one of: {choices}") from error


def site_output_dir(site: str) -> Path:
    output = PROCESSED_DATA_DIR / site
    output.mkdir(parents=True, exist_ok=True)
    return output
