"""Prepare one Moon planning site from windowed lunar source rasters."""

import argparse
import json
import math
import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling
from rasterio.transform import Affine
from rasterio.crs import CRS
from rasterio.warp import reproject, transform as warp_transform
from rasterio.windows import from_bounds
from scipy import ndimage

from config import (
    ALTERNATE_ROUTE_COST_MULTIPLIER,
    ALTERNATE_ROUTE_CORRIDOR_CELLS,
    ALTERNATE_ROUTE_MAX_OVERLAP,
    ALTERNATE_ROUTE_MAX_TIME_FACTOR,
    ALTERNATE_ROUTE_MIN_LEG_CELLS,
    BODIES,
    CLEARANCE_COST_RADIUS_CELLS,
    CLEARANCE_COST_WEIGHT,
    MAX_ROUGHNESS_M,
    MAX_WALKABLE_SLOPE_DEG,
    MOON_EVA_HOURS,
    MOON_RADIUS_M,
    MOON_WALKING_SPEED_KMH,
    PROJECT_ROOT,
    SAFETY_MARGIN_CELLS,
    SAFER_CLEARANCE_COST_WEIGHT,
    WEIGHTED_ASTAR_EPSILON,
)
from route import (
    astar,
    build_walkable_mask,
    distance_to_hazards,
    make_route_cost_grid,
    passability_metrics,
    route_distance_km,
)
from slope import (
    build_hazard_mask,
    calculate_roughness,
    calculate_slope,
    rgba_from_scalar,
    write_png,
)

BODY = BODIES["moon"]
RAW_DIR = BODY["raw_dir"]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "moon"
WEB_DIR = PROJECT_ROOT / "web" / "data" / "moon"
GRID_SIZE_M = int(BODY["layers"]["routing_resolution_m"])
GRID_SHAPE = (500, 500)
NODATA_FLOAT = -9999.0
COUNT_SITE_KEYS = {
    site["region_id"]: key
    for key, site in BODY["sites"].items()
    if site["region_id"] is not None
}


def lon_lat_to_xy(latitude: float, longitude: float) -> tuple[float, float]:
    """Project longitude/latitude to the south-polar stereographic sphere."""
    latitude_rad = math.radians(latitude)
    longitude_rad = math.radians(longitude)
    rho = 2 * MOON_RADIUS_M * math.tan(math.pi / 4 + latitude_rad / 2)
    return rho * math.sin(longitude_rad), rho * math.cos(longitude_rad)


def xy_to_lon_lat(x: float, y: float) -> tuple[float, float]:
    rho = math.hypot(x, y)
    latitude = 2 * math.atan(rho / (2 * MOON_RADIUS_M)) - math.pi / 2
    longitude = math.atan2(x, y)
    return math.degrees(latitude), math.degrees(longitude)


def valid_data(values: np.ndarray, nodata: float | int | None) -> np.ndarray:
    valid = np.isfinite(values)
    if nodata is not None and np.isfinite(nodata):
        valid &= values != nodata
    return valid


def project_window(
    source: rasterio.DatasetReader,
    bounds: tuple[float, float, float, float],
    shape: tuple[int, int],
    dtype: str = "float32",
    resampling: Resampling = Resampling.average,
) -> np.ndarray:
    left, bottom, right, top = bounds
    transform = Affine(
        (right - left) / shape[1], 0, left,
        0, -(top - bottom) / shape[0], top,
    )
    window = from_bounds(*bounds, transform=source.transform)
    result = np.full(shape, np.nan, dtype=dtype)
    reproject(
        source=rasterio.band(source, 1),
        destination=result,
        src_transform=source.transform,
        src_crs=source.crs,
        src_nodata=source.nodata,
        src_window=window,
        dst_transform=transform,
        dst_crs=source.crs,
        dst_nodata=np.nan if np.issubdtype(np.dtype(dtype), np.floating) else 0,
        resampling=resampling,
        num_threads=1,
        init_dest_nodata=True,
    )
    return result


def projected_bounds(center_x: float, center_y: float) -> tuple[float, float, float, float]:
    half_size = GRID_SHAPE[0] * GRID_SIZE_M / 2
    left = math.floor((center_x - half_size) / GRID_SIZE_M) * GRID_SIZE_M
    bottom = math.floor((center_y - half_size) / GRID_SIZE_M) * GRID_SIZE_M
    return left, bottom, left + GRID_SHAPE[1] * GRID_SIZE_M, bottom + GRID_SHAPE[0] * GRID_SIZE_M


def geojson_features() -> list[dict]:
    path = RAW_DIR / BODY["regions_file"]
    document = json.loads(path.read_text())
    if "crs" in document:
        raise ValueError("Named-region GeoJSON has an unexpected explicit CRS")
    if document.get("type") != "FeatureCollection":
        raise ValueError("Named-region input must be a GeoJSON FeatureCollection")
    return document["features"]


def find_site_center(site_key: str, features: list[dict]) -> tuple[float, float]:
    site = BODY["sites"][site_key]
    region_id = site["region_id"]
    if region_id is None:
        surface_path = RAW_DIR / site["surface_file"]
        with rasterio.open(surface_path) as source:
            return (
                (source.bounds.left + source.bounds.right) / 2,
                (source.bounds.bottom + source.bounds.top) / 2,
            )
    matches = [
        feature for feature in features
        if str(feature.get("id")) == str(region_id)
        or feature.get("properties", {}).get("id") == region_id
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected one GeoJSON feature for {site_key} id {region_id}")
    feature = matches[0]
    properties = feature.get("properties", {})
    actual_name = properties.get("label")
    if actual_name != site["label"]:
        raise ValueError(
            f"{site_key} label {site['label']!r} does not match GeoJSON "
            f"{actual_name!r}; property keys: {sorted(properties)}"
        )
    coordinates = feature["geometry"]["coordinates"]
    ring = (
        coordinates[0]
        if feature["geometry"]["type"] == "Polygon"
        else coordinates[0][0]
    )
    projected = [
        lon_lat_to_xy(float(latitude), float(longitude))
        for longitude, latitude, *_ in ring[:-1]
    ]
    return (
        sum(point[0] for point in projected) / len(projected),
        sum(point[1] for point in projected) / len(projected),
    )


def verify_projection_against_source(features: list[dict], source_crs) -> None:
    points = []
    for feature in features:
        feature_id = feature.get("id", feature.get("properties", {}).get("id"))
        try:
            feature_id = int(feature_id)
        except (TypeError, ValueError):
            continue
        if feature_id not in (5, 6, 8):
            continue
        geometry = feature["geometry"]
        coordinates = geometry["coordinates"]
        ring = coordinates[0] if geometry["type"] == "Polygon" else coordinates[0][0]
        longitude, latitude = map(float, ring[0][:2])
        points.append((longitude, latitude))
    if len(points) != 3:
        raise ValueError(f"Expected 3 reference GeoJSON points; found {len(points)}")
    longitudes, latitudes = zip(*points)
    source_x, source_y = warp_transform(
        CRS.from_proj4(f"+proj=longlat +R={MOON_RADIUS_M} +no_defs +type=crs"),
        source_crs,
        list(longitudes),
        list(latitudes),
    )
    for (longitude, latitude), expected_x, expected_y in zip(
        points, source_x, source_y
    ):
        actual_x, actual_y = lon_lat_to_xy(latitude, longitude)
        error_m = math.hypot(actual_x - expected_x, actual_y - expected_y)
        if error_m > 1:
            raise ValueError(
                f"Polar projection differs from source CRS by {error_m:.3f} m"
            )


def rgba_with_validity(values: np.ndarray, valid: np.ndarray) -> np.ndarray:
    return rgba_from_scalar(values, valid & np.isfinite(values))


def write_float_raster(
    path: Path,
    values: np.ndarray,
    transform: Affine,
    crs,
    tags: dict[str, str],
) -> None:
    profile = {
        "driver": "GTiff",
        "width": values.shape[1],
        "height": values.shape[0],
        "count": 1,
        "dtype": "float32",
        "crs": crs,
        "transform": transform,
        "nodata": NODATA_FLOAT,
        "compress": "deflate",
        "predictor": 3,
    }
    with rasterio.open(path, "w", **profile) as output:
        output.write(np.where(np.isfinite(values), values, NODATA_FLOAT).astype("float32"), 1)
        output.update_tags(**tags)


def save_hillshade(dem_path: Path, dem: np.ndarray, output_path: Path) -> None:
    environment = os.environ.copy()
    environment["GDAL_CACHEMAX"] = "64"
    environment["GDAL_PAM_ENABLED"] = "NO"
    with tempfile.TemporaryDirectory(prefix="moon-hillshade-") as directory:
        hillshade_path = Path(directory) / "hillshade.tif"
        subprocess.run(
            [
                "gdaldem", "hillshade", "-q", "-compute_edges", "-of", "GTiff",
                str(dem_path), str(hillshade_path),
            ],
            check=True,
            env=environment,
        )
        with rasterio.open(hillshade_path) as source:
            values = source.read(1, out_shape=GRID_SHAPE, resampling=Resampling.nearest)
            valid = np.isfinite(dem)
        write_png(output_path, rgba_with_validity(values, valid))


def choose_placeholders(walkable: np.ndarray) -> tuple[dict, list[dict]]:
    structure = ndimage.generate_binary_structure(2, 1)
    labels, component_count = ndimage.label(walkable, structure=structure)
    if component_count == 0:
        return {}, []
    counts = np.bincount(labels.ravel(), minlength=component_count + 1)
    counts[0] = 0
    largest_label = int(np.argmax(counts))
    cells = np.argwhere(labels == largest_label)
    if len(cells) < 4:
        return {}, []

    center = np.array([(walkable.shape[0] - 1) / 2, (walkable.shape[1] - 1) / 2])

    def nearest(target: np.ndarray, excluded: set[tuple[int, int]]) -> tuple[int, int]:
        for row, col in cells[np.argsort(np.sum((cells - target) ** 2, axis=1))]:
            cell = (int(row), int(col))
            if cell not in excluded:
                return cell
        raise ValueError("Could not select four distinct placeholder cells")

    habitat = nearest(center, set())
    used = {habitat}
    targets = []
    for desired in (
        np.array([125.0, 125.0]),
        np.array([125.0, 375.0]),
        np.array([375.0, 250.0]),
    ):
        cell = nearest(desired, used)
        used.add(cell)
        targets.append(cell)
    return (
        {"id": "habitat", "row": habitat[0], "col": habitat[1], "placeholder": True},
        [
            {
                "id": f"target-{index + 1}",
                "name": f"PLACEHOLDER target {index + 1}",
                "row": row,
                "col": col,
                "placeholder": True,
            }
            for index, (row, col) in enumerate(targets)
        ],
    )


def write_route_cost(
    site_key: str,
    costs: np.ndarray,
    clearance_cells: np.ndarray,
    clearance_meters: np.ndarray,
    transform: Affine,
    crs,
    bounds: tuple[float, float, float, float],
) -> dict:
    output = WEB_DIR / site_key
    output.mkdir(parents=True, exist_ok=True)
    costs.astype("<f4").tofile(output / "cost.bin")
    clearance_cells.astype("<f4").tofile(output / "clearance_cells.bin")
    clearance_meters.astype("<f4").tofile(output / "clearance_meters.bin")
    metadata = {
        "format_version": 2,
        "body": "moon",
        "site": site_key,
        "data_status": "REAL - derived from supplied NASA DEM products",
        "rows": costs.shape[0],
        "cols": costs.shape[1],
        "cell_size_m": {"x": GRID_SIZE_M, "y": GRID_SIZE_M},
        "raster_transform": list(transform)[:6],
        "crs_wkt": crs.to_wkt(),
        "bounds": {
            "min_x": bounds[0],
            "min_y": bounds[1],
            "max_x": bounds[2],
            "max_y": bounds[3],
        },
        "cost_file": "cost.bin",
        "clearance_files": {
            "cells": "clearance_cells.bin",
            "meters": "clearance_meters.bin",
        },
        "parameters": {
            "safety_margin_cells": SAFETY_MARGIN_CELLS,
            "clearance_cost_radius_cells": CLEARANCE_COST_RADIUS_CELLS,
            "clearance_cost_weight": CLEARANCE_COST_WEIGHT,
            "max_walkable_slope_deg": MAX_WALKABLE_SLOPE_DEG,
            "max_roughness_m": MAX_ROUGHNESS_M,
            "walking_speed_kmh": MOON_WALKING_SPEED_KMH,
            "eva_hours": MOON_EVA_HOURS,
            "dose_rate_msv_per_hour": None,
            "dose_status": "not computed: no lunar radiation source integrated",
            "weighted_astar_epsilon": WEIGHTED_ASTAR_EPSILON,
            "safer_clearance_cost_weight": SAFER_CLEARANCE_COST_WEIGHT,
            "alternate_route_cost_multiplier": ALTERNATE_ROUTE_COST_MULTIPLIER,
            "alternate_route_corridor_cells": ALTERNATE_ROUTE_CORRIDOR_CELLS,
            "alternate_route_min_leg_cells": ALTERNATE_ROUTE_MIN_LEG_CELLS,
            "alternate_route_max_overlap": ALTERNATE_ROUTE_MAX_OVERLAP,
            "alternate_route_max_time_factor": ALTERNATE_ROUTE_MAX_TIME_FACTOR,
        },
        "dtype": "float32",
        "byte_order": "little-endian",
        "layout": "row-major",
        "hazard_cost": "positive-infinity",
    }
    (output / "cost.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


def write_background_and_regions(
    features: list[dict],
    site_entries: list[dict],
) -> None:
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    rough_path = RAW_DIR / BODY["roughness_file"]
    with rasterio.open(rough_path) as source:
        decimated_shape = (max(1, source.height // 2), max(1, source.width // 2))
        roughness = source.read(
            1, out_shape=decimated_shape, resampling=Resampling.average
        ).astype("float32")
        rough_transform = source.transform * Affine.scale(
            source.width / decimated_shape[1],
            source.height / decimated_shape[0],
        )
        rough_valid = valid_data(roughness, source.nodata)
        rough_bounds = source.bounds
    write_png(WEB_DIR / "roughness_backdrop.png", rgba_with_validity(roughness, rough_valid))
    (WEB_DIR / "backdrop.json").write_text(json.dumps({
        "data_status": "REAL - NASA LOLA roughness product",
        "product": BODY["roughness_file"],
        "source_resolution_m": 1000,
        "overview_shape": list(decimated_shape),
        "bounds": {
            "min_x": rough_bounds.left,
            "min_y": rough_bounds.bottom,
            "max_x": rough_bounds.right,
            "max_y": rough_bounds.top,
        },
        "transform": list(rough_transform)[:6],
        "coordinate_system": "South polar stereographic, meters",
        "radius_m": MOON_RADIUS_M,
        "image": "roughness_backdrop.png",
    }, indent=2) + "\n")

    regions = []
    projection_checks = []
    for feature in features:
        properties = feature.get("properties", {})
        region_id = feature.get("id", properties.get("id"))
        try:
            normalized_region_id = int(region_id)
        except (TypeError, ValueError):
            normalized_region_id = region_id
        name = properties.get("label", "Unnamed region")
        geometry = feature["geometry"]
        rings = geometry["coordinates"] if geometry["type"] == "Polygon" else geometry["coordinates"]
        projected_rings = []
        for polygon in rings:
            projected_rings.append([
                list(lon_lat_to_xy(float(lat), float(lon)))
                for lon, lat, *_ in polygon
            ])
        if normalized_region_id in (5, 6, 8):
            source_point = rings[0][0]
            longitude, latitude = map(float, source_point[:2])
            x, y = lon_lat_to_xy(latitude, longitude)
            round_trip_lat, round_trip_lon = xy_to_lon_lat(x, y)
            round_trip_error_m = math.hypot(
                math.radians(round_trip_lat - latitude) * MOON_RADIUS_M,
                math.radians(round_trip_lon - longitude) * MOON_RADIUS_M
                    * math.cos(math.radians(latitude)),
            )
            if round_trip_error_m > 1:
                raise ValueError(
                    f"Moon projection inverse differs by {round_trip_error_m:.3f} m"
                )
            projection_checks.append({
                "region_id": region_id,
                "longitude": longitude,
                "latitude": latitude,
                "x": x,
                "y": y,
                "python_round_trip_error_m": round_trip_error_m,
            })
        site_key = COUNT_SITE_KEYS.get(normalized_region_id)
        has_data = any(item["key"] == site_key for item in site_entries)
        regions.append({
            "type": "Feature",
            "id": region_id,
            "properties": {
                "name": name,
                "source_id": region_id,
                "site_key": site_key if has_data else None,
                "has_elevation_data": has_data,
            },
            "geometry": {
                "type": geometry["type"],
                "coordinates": projected_rings,
            },
        })

    (WEB_DIR / "regions.json").write_text(json.dumps({
        "type": "FeatureCollection",
        "coordinate_system": "Moon south polar stereographic meters",
        "features": regions,
    }, indent=2) + "\n")
    default_site = BODY["default_site"]
    if not any(site["key"] == default_site for site in site_entries):
        default_site = site_entries[0]["key"] if site_entries else None
    (WEB_DIR / "body.json").write_text(json.dumps({
        "body": "moon",
        "label": "Moon",
        "radius_m": MOON_RADIUS_M,
        "default_site": default_site,
        "sites": site_entries,
        "projection_checks": projection_checks,
        "layers": {
            "roughness": BODY["layers"]["roughness"],
            "count": BODY["layers"]["count"],
            "site_resolution_m": BODY["layers"]["site_resolution_m"],
            "routing_resolution_m": BODY["layers"]["routing_resolution_m"],
            "slope_uncertainty_degrees": BODY["layers"]["slope_uncertainty_degrees"],
        },
        "backdrop": "web/data/moon/roughness_backdrop.png",
        "backdrop_metadata": "data/moon/backdrop.json",
        "regions": "data/moon/regions.json",
        "labels": {
            "data_support": "LOLA laser-return support",
            "dose": "not computed: no lunar radiation source integrated",
            "assumptions": [
                "walking speed",
                "EVA hours",
                "slope limit",
                "habitat and targets are PLACEHOLDERS",
            ],
            "data_note": (
                "Most 5 m surface pixels are interpolated; the support layer shows "
                "where measured LOLA returns exist. Slope uncertainty is roughly "
                "1.5 to 2.5 degrees."
            ),
            "not_integrated": BODY["layers"]["not_integrated"],
        },
    }, indent=2) + "\n")


def site_manifest_entry(site_key: str) -> dict:
    site_root = PROCESSED_DIR / site_key
    stats_path = site_root / "stats.json"
    grid_path = site_root / "grid.json"
    if not stats_path.is_file() or not grid_path.is_file():
        return {}
    stats = json.loads(stats_path.read_text())
    grid = json.loads(grid_path.read_text())
    coverage = stats["lola_return_pixel_fraction"] * 100
    return {
        "key": site_key,
        "name": BODY["sites"][site_key]["label"],
        "descriptor": (
            f"{stats['hazard_fraction']:.0%} hazard, "
            f"{coverage:.1f}% of source 5 m pixels have LOLA returns"
        ),
        "region_id": BODY["sites"][site_key]["region_id"],
        "bounds": grid["geo_reference"]["bounds"],
        "grid": f"data/processed/moon/{site_key}/grid.json",
        "cost": f"data/moon/{site_key}/cost.json",
        "assets": grid["layer_paths"],
        "metrics": stats,
        "source_products": {
            "surface": BODY["sites"][site_key]["surface_file"],
            "slope": BODY["sites"][site_key]["slope_file"],
            "source_resolution_m": BODY["layers"]["site_resolution_m"],
            "routing_resolution_m": BODY["layers"]["routing_resolution_m"],
        },
    }


def process_site(site_key: str) -> None:
    if site_key not in BODY["sites"]:
        raise ValueError(f"Unknown Moon site {site_key!r}")
    features = geojson_features()
    center_x, center_y = find_site_center(site_key, features)
    bounds = projected_bounds(center_x, center_y)
    left, bottom, right, top = bounds
    transform = Affine(GRID_SIZE_M, 0, left, 0, -GRID_SIZE_M, top)
    output = PROCESSED_DIR / site_key
    output.mkdir(parents=True, exist_ok=True)
    site = BODY["sites"][site_key]
    surface_path = RAW_DIR / site["surface_file"]
    slope_path = RAW_DIR / site["slope_file"]

    with rasterio.open(surface_path) as surface:
        dem = project_window(surface, bounds, GRID_SHAPE)
        source_crs = surface.crs
        source_bounds = surface.bounds
    verify_projection_against_source(features, source_crs)
    with rasterio.open(slope_path) as slope_source:
        supplied_slope = project_window(slope_source, bounds, GRID_SHAPE)
    with rasterio.open(RAW_DIR / BODY["count_file"]) as count_source:
        support_counts = project_window(
            count_source, bounds, GRID_SHAPE, dtype="float32",
            resampling=Resampling.max,
        )
        count_window = from_bounds(*bounds, transform=count_source.transform)
        exact_counts = count_source.read(1, window=count_window, boundless=False)
        support_fraction = float(np.count_nonzero(exact_counts > 0) / exact_counts.size)

    dem_valid = np.isfinite(dem)
    if not np.any(dem_valid):
        raise ValueError(f"{site_key} selected planning bounds contain only NoData")
    supplied_slope_valid = np.isfinite(supplied_slope)
    computed_slope = calculate_slope(
        dem, GRID_SIZE_M, GRID_SIZE_M, dem_valid
    )
    roughness = calculate_roughness(dem, dem_valid)
    comparison_valid = (
        supplied_slope_valid
        & np.isfinite(computed_slope)
        & dem_valid
    )
    slope_mad = (
        float(np.mean(np.abs(supplied_slope[comparison_valid] - computed_slope[comparison_valid])))
        if np.any(comparison_valid)
        else None
    )
    hazard = build_hazard_mask(
        supplied_slope,
        roughness,
        MAX_WALKABLE_SLOPE_DEG,
        MAX_ROUGHNESS_M,
    )
    clearance_cells, clearance_meters = distance_to_hazards(
        hazard, GRID_SIZE_M, GRID_SIZE_M
    )
    costs = make_route_cost_grid(
        supplied_slope, roughness, hazard, clearance_cells
    )
    walkable = build_walkable_mask(costs, clearance_cells, SAFETY_MARGIN_CELLS)
    largest_fraction, chokepoints = passability_metrics(walkable)

    tags = {
        "DATA_STATUS": "REAL - derived from supplied NASA LOLA products",
        "SOURCE_SURFACE": site["surface_file"],
        "SOURCE_SLOPE": site["slope_file"],
        "SLOPE_USED_FOR_HAZARD": "supplied slope raster, average-resampled to 10 m",
        "SLOPE_COMPARISON": "mean absolute difference against calculated degree slope",
        "SLOPE_MAD_DEGREES": "not available" if slope_mad is None else f"{slope_mad:.6f}",
        "CELL_SIZE_M": str(GRID_SIZE_M),
        "HAZARD_ENCODING": "1=slope_or_roughness_or_nodata",
    }
    write_float_raster(output / "elevation.tif", dem, transform, source_crs, tags)
    write_float_raster(output / "slope.tif", supplied_slope, transform, source_crs, tags)
    write_float_raster(output / "roughness.tif", roughness, transform, source_crs, tags)
    with rasterio.open(output / "hazard.tif", "w", driver="GTiff",
                       width=GRID_SHAPE[1], height=GRID_SHAPE[0], count=1,
                       dtype="uint8", crs=source_crs, transform=transform,
                       compress="deflate") as target:
        target.write(hazard.astype("uint8"), 1)
        target.update_tags(**tags)
    support_valid = np.isfinite(support_counts) & (support_counts > 0)
    support_counts[~np.isfinite(support_counts)] = 0
    with rasterio.open(output / "support.tif", "w", driver="GTiff",
                       width=GRID_SHAPE[1], height=GRID_SHAPE[0], count=1,
                       dtype="float32", crs=source_crs, transform=transform,
                       nodata=0, compress="deflate", predictor=3) as target:
        target.write(support_counts.astype("float32"), 1)
        target.update_tags(
            DATA_STATUS="REAL - windowed LOLA count raster",
            SOURCE_PRODUCT=BODY["count_file"],
            ENCODING="positive=one or more recorded returns",
        )

    write_png(output / "elevation.png", rgba_with_validity(dem, dem_valid))
    write_png(
        output / "slope.png",
        rgba_with_validity(supplied_slope, supplied_slope_valid),
    )
    write_png(
        output / "hazard.png",
        np.dstack((
            np.where(hazard, 239, 0),
            np.where(hazard, 68, 0),
            np.where(hazard, 68, 0),
            np.where(hazard, 220, 0),
        )).astype("uint8"),
    )
    write_png(
        output / "support.png",
        rgba_with_validity(support_counts, support_valid),
    )
    save_hillshade(output / "elevation.tif", dem, output / "hillshade.png")

    habitat, targets = choose_placeholders(walkable)
    route_segments = []
    route_pixels = []
    if habitat and targets:
        endpoints = [habitat, *targets, habitat]
        for start, goal in zip(endpoints, endpoints[1:]):
            route_segments.append(astar(
                (start["row"], start["col"]),
                (goal["row"], goal["col"]),
                walkable,
                costs,
                GRID_SIZE_M,
                GRID_SIZE_M,
            ))
        for segment in route_segments:
            route_pixels.extend(segment if not route_pixels else segment[1:])
    route_distance_m = route_distance_km(route_pixels, GRID_SIZE_M, GRID_SIZE_M) * 1000 if route_pixels else None
    route_time_h = route_distance_m / 1000 / MOON_WALKING_SPEED_KMH if route_distance_m is not None else None

    min_elevation = float(np.nanmin(dem))
    max_elevation = float(np.nanmax(dem))
    elevation_std = float(np.nanstd(dem))
    stats = {
        "data_status": "REAL - NASA lunar raster products; placeholders are labeled",
        "site": site_key,
        "site_name": site["label"],
        "center_xy_m": {"x": center_x, "y": center_y},
        "bounds_xy_m": {"min_x": left, "min_y": bottom, "max_x": right, "max_y": top},
        "source_raster_bounds_xy_m": {
            "min_x": source_bounds.left,
            "min_y": source_bounds.bottom,
            "max_x": source_bounds.right,
            "max_y": source_bounds.top,
        },
        "cell_size_m": {"x": GRID_SIZE_M, "y": GRID_SIZE_M},
        "elevation_min": min_elevation,
        "elevation_max": max_elevation,
        "elevation_std": elevation_std,
        "nodata_cells": int(np.count_nonzero(~dem_valid)),
        "slope_source_mean_absolute_difference_degrees": slope_mad,
        "slope_comparison_cells": int(comparison_valid.sum()),
        "lola_return_pixel_fraction": support_fraction,
        "hazard_cells": int(hazard.sum()),
        "hazard_fraction": float(hazard.mean()),
        "largest_passable_component_fraction": largest_fraction,
        "chokepoints": chokepoints,
        "safety_margin_cells": SAFETY_MARGIN_CELLS,
        "route_distance_km": None if route_distance_m is None else route_distance_m / 1000,
        "route_time_h": route_time_h,
        "return_margin_h": None if route_time_h is None else MOON_EVA_HOURS - route_time_h,
        "within_eva_limit": None if route_time_h is None else route_time_h <= MOON_EVA_HOURS,
        "dose_status": "not computed: no lunar radiation source integrated",
        "thresholds": {
            "max_walkable_slope_deg": MAX_WALKABLE_SLOPE_DEG,
            "max_roughness_m": MAX_ROUGHNESS_M,
        },
        "assumptions": [
            "walking speed",
            "EVA hours",
            "slope limit",
            "roughness limit",
            "habitat and targets",
        ],
    }
    (output / "stats.json").write_text(json.dumps(stats, indent=2) + "\n")
    layer_paths = {
        "hillshade": f"data/processed/moon/{site_key}/hillshade.png",
        "slope": f"data/processed/moon/{site_key}/slope.png",
        "hazard": f"data/processed/moon/{site_key}/hazard.png",
        "support": f"data/processed/moon/{site_key}/support.png",
        "elevation": f"data/processed/moon/{site_key}/elevation.png",
    }
    grid = {
        "data_status": stats["data_status"],
        "body": "moon",
        "site": site_key,
        "site_name": site["label"],
        "rows": GRID_SHAPE[0],
        "cols": GRID_SHAPE[1],
        "grid_bounds": [[0, 0], list(GRID_SHAPE)],
        "geo_reference": {
            "status": "REAL - source raster extent, windowed to selected planning box",
            "bounds": {
                "min_x": left,
                "min_y": bottom,
                "max_x": right,
                "max_y": top,
            },
            "transform": list(transform)[:6],
            "cell_centers": True,
            "coordinate_system": "Moon south polar stereographic meters",
        },
        "cell_size_m": {"x": GRID_SIZE_M, "y": GRID_SIZE_M},
        "max_walkable_slope_deg": MAX_WALKABLE_SLOPE_DEG,
        "max_roughness_m": MAX_ROUGHNESS_M,
        "safety_margin_cells": SAFETY_MARGIN_CELLS,
        "habitat": habitat,
        "targets": targets,
        "route_pixels": route_pixels,
        "route_segments": route_segments,
        "route_status": "PLACEHOLDER route" if route_pixels else "No connected route available",
        "coordinate_status": "PLACEHOLDER - demonstration habitat and targets",
        "layer_paths": layer_paths,
    }
    (output / "grid.json").write_text(json.dumps(grid) + "\n")
    write_route_cost(
        site_key, costs, clearance_cells, clearance_meters,
        transform, source_crs, bounds,
    )
    site_entries = [
        entry for key in BODY["sites"]
        if (entry := site_manifest_entry(key))
    ]
    write_background_and_regions(features, site_entries)

    oversized = [
        path for path in output.iterdir()
        if path.is_file() and path.stat().st_size > 5 * 1024 * 1024
    ]
    if oversized:
        raise ValueError(
            "Moon site output exceeds 5 MB: "
            + ", ".join(path.name for path in oversized)
        )
    for path in (WEB_DIR / "roughness_backdrop.png",):
        if path.stat().st_size > 3 * 1024 * 1024:
            raise ValueError(f"{path.name} exceeds 3 MB")

    print(
        f"{site_key}: cell={GRID_SIZE_M} m; elevation min/max/std="
        f"{min_elevation:.3f}/{max_elevation:.3f}/{elevation_std:.3f}; "
        f"NoData={int((~dem_valid).sum())}; supplied-vs-calculated slope "
        f"mean absolute difference={slope_mad:.4f} degrees "
        f"({int(comparison_valid.sum())} cells); "
        f"LOLA return coverage={support_fraction:.4%}; "
        f"hazard={hazard.mean():.2%}; largest passable component="
        f"{largest_fraction:.2%}; chokepoints={chokepoints}; "
        f"auto route={route_distance_m / 1000:.3f} km / {route_time_h:.3f} h"
        if route_distance_m is not None else
        f"{site_key}: cell={GRID_SIZE_M} m; elevation min/max/std="
        f"{min_elevation:.3f}/{max_elevation:.3f}/{elevation_std:.3f}; "
        f"NoData={int((~dem_valid).sum())}; supplied-vs-calculated slope "
        f"mean absolute difference={slope_mad}; LOLA return coverage="
        f"{support_fraction:.4%}; hazard={hazard.mean():.2%}; "
        f"largest passable component={largest_fraction:.2%}; "
        f"chokepoints={chokepoints}; no connected auto route"
    )
    for path in sorted(output.iterdir()):
        if path.is_file():
            print(f"  {path.name}: {path.stat().st_size} bytes")
    for path in sorted((WEB_DIR / site_key).iterdir()):
        if path.is_file():
            print(f"  web/{site_key}/{path.name}: {path.stat().st_size} bytes")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", choices=sorted(BODY["sites"]), required=True)
    args = parser.parse_args()
    process_site(args.site)


if __name__ == "__main__":
    main()
