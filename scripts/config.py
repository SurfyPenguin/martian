"""Site configuration and adjustable EVA assumptions."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
MARS_RADIUS_M = 3_389_500.0
MOON_RADIUS_M = 1_737_400.0

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
    "site3": {
        "name": "Rough terrain box",
        "provenance": (
            "NASA-provided clipped DEM and CTX input; product ID and acquisition "
            "date were not supplied."
        ),
        "dem_path": PROCESSED_DATA_DIR / "site3_dem.tif",
        "imagery_path": PROCESSED_DATA_DIR / "site3_imagery.tif",
        # Nominal requested bounds; grid.json contains authoritative raster extents.
        "bounds": {
            "min_lon": 137.3376,
            "min_lat": -4.7423,
            "max_lon": 137.4224,
            "max_lat": -4.6577,
        },
        "limitations_note": (
            "Model uses slope and roughness only. It cannot see loose sand or "
            "sharp embedded rocks, so real difficulty may be higher."
        ),
        # PLACEHOLDER coordinates: demo choices, not mission-validated.
        "habitat": {"lat": -4.6993585, "lon": 137.3792585},
        "targets": [
            {"lat": -4.7404255, "lon": 137.3390365},
            {"lat": -4.6633615, "lon": 137.3691185},
            {"lat": -4.7301165, "lon": 137.4215085},
        ],
    },
    "site4": {
        "name": "Dune-edge box",
        "provenance": (
            "NASA-provided clipped DEM and CTX input; product ID and acquisition "
            "date were not supplied."
        ),
        "dem_path": PROCESSED_DATA_DIR / "site4_dem.tif",
        "imagery_path": PROCESSED_DATA_DIR / "site4_imagery.tif",
        # Nominal requested bounds; grid.json contains authoritative raster extents.
        "bounds": {
            "min_lon": 137.3776,
            "min_lat": -4.9223,
            "max_lon": 137.4624,
            "max_lat": -4.8377,
        },
        "limitations_note": (
            "Model uses slope and roughness only. It cannot see loose sand or "
            "sharp embedded rocks, so real difficulty may be higher."
        ),
        # PLACEHOLDER coordinates: demo choices, not mission-validated.
        "habitat": {"lat": -4.8528255, "lon": 137.3900215},
        "targets": [
            {"lat": -4.8744575, "lon": 137.3800505},
            {"lat": -4.8384605, "lon": 137.4104705},
            {"lat": -4.8418405, "lon": 137.3795435},
        ],
    },
}

# ASSUMPTION: lunar EVA walking speed; no mission-specific speed was supplied.
MOON_WALKING_SPEED_KMH = 3.0
# ASSUMPTION: lunar EVA duration; no mission-specific limit was supplied.
MOON_EVA_HOURS = 4.0

# ASSUMPTION: maximum slope considered walkable by a suited astronaut.
MAX_WALKABLE_SLOPE_DEG = 15.0
# ASSUMPTION: local 5x5 elevation standard deviation above this value is
# considered too rough for the planned EVA.
MAX_ROUGHNESS_M = 15.0
# ASSUMPTION: keep this many cells clear between a route and any hazard.
SAFETY_MARGIN_CELLS = 2

# These are the supplied raster identifiers. Named-region labels are checked
# against the GeoJSON by make_moon_site.py; site_04 has no matching feature.
BODIES = {
    "mars": {
        "label": "Mars",
        "radius_m": MARS_RADIUS_M,
        "sites": SITES,
    },
    "moon": {
        "label": "Moon",
        "radius_m": MOON_RADIUS_M,
        "raw_dir": PROJECT_ROOT / "data" / "raw" / "moon",
        "regions_file": "A3_Named_regions_SP.geojson",
        "roughness_file": "LDRM_80S_1000MPP_ADJ_ROUGH_100M.tiff",
        "count_file": "LRO_LOLA_Count_SPole875_5mp_v04.tif",
        "default_site": "site_01",
        "layers": {
            "roughness": {
                "label": "Roughness backdrop",
                "product": "LDRM_80S_1000MPP_ADJ_ROUGH_100M.tiff",
                "resolution_m": 1000,
            },
            "count": {
                "label": "LOLA laser-return support",
                "product": "LRO_LOLA_Count_SPole875_5mp_v04.tif",
                "resolution_m": 5,
            },
            "site_resolution_m": 5,
            "routing_resolution_m": 10,
            "slope_uncertainty_degrees": [1.5, 2.5],
            "not_integrated": [
                "illumination",
                "temperature",
                "radiation",
                "imagery",
            ],
        },
        "assumptions": {
            # ASSUMPTION: reuse the configured conservative slope threshold.
            "max_walkable_slope_deg": MAX_WALKABLE_SLOPE_DEG,
            # ASSUMPTION: reuse the configured roughness threshold.
            "max_roughness_m": MAX_ROUGHNESS_M,
            "safety_margin_cells": SAFETY_MARGIN_CELLS,
            "walking_speed_kmh": MOON_WALKING_SPEED_KMH,
            "eva_hours": MOON_EVA_HOURS,
            "dose_rate_msv_per_hour": None,
        },
        "sites": {
            "site_01": {
                "label": "Connecting Ridge",
                "region_id": 6,
                "surface_file": "site_01_final_adj_5mpp_surf.tif",
                "slope_file": "site_01_final_adj_5mpp_slp.tif",
            },
            "site_04": {
                "label": "site_04 raster (unmatched named region)",
                "region_id": None,
                "surface_file": "site_04_final_adj_5mpp_surf.tif",
                "slope_file": "site_04_final_adj_5mpp_slp.tif",
            },
            "site_07": {
                "label": "Peak Near Shakleton",
                "region_id": 8,
                "surface_file": "site_07_final_adj_5mpp_surf.tif",
                "slope_file": "site_07_final_adj_5mpp_slp.tif",
            },
            "sl3": {
                "label": "Connecting Ridge Extension",
                "region_id": 5,
                "surface_file": "sl3_final_adj_5mpp_surf.tif",
                "slope_file": "sl3_final_adj_5mpp_slp.tif",
            },
        },
    },
}

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
