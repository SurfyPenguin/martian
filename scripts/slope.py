"""Build slope, roughness, hazard, and browser rasters for one real site."""

import argparse
import math
import os
import subprocess
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from numpy.lib.stride_tricks import sliding_window_view
from rasterio.warp import reproject

from config import (
    MARS_RADIUS_M,
    MAX_ROUGHNESS_M,
    MAX_WALKABLE_SLOPE_DEG,
    SITES,
    site_config,
    site_output_dir,
)


def cell_size_meters(source: rasterio.DatasetReader) -> tuple[float, float]:
    """Convert the DEM's angular pixel size to Mars meters."""
    x_size_deg, y_size_deg = source.res
    if source.crs is None or not source.crs.is_geographic:
        raise ValueError("The real DEM must have a geographic CRS in degrees")
    latitude = math.radians((source.bounds.top + source.bounds.bottom) / 2)
    meters_per_degree = MARS_RADIUS_M * math.pi / 180
    return (
        abs(x_size_deg) * meters_per_degree * math.cos(latitude),
        abs(y_size_deg) * meters_per_degree,
    )


def calculate_slope(
    dem: np.ndarray,
    x_size_m: float,
    y_size_m: float,
    valid: np.ndarray,
) -> np.ndarray:
    """Calculate degree slope without using invalid elevation values."""
    rows, cols = dem.shape
    dz_dx = np.full(dem.shape, np.nan, dtype="float64")
    dz_dy = np.full(dem.shape, np.nan, dtype="float64")

    if cols > 1:
        forward = valid[:, :-1] & valid[:, 1:]
        dz_dx[:, :-1][forward] = (
            (dem[:, 1:] - dem[:, :-1]) / x_size_m
        )[forward]
        dz_dx[:, 1:][forward] = dz_dx[:, :-1][forward]
    if rows > 1:
        forward = valid[:-1, :] & valid[1:, :]
        dz_dy[:-1, :][forward] = (
            (dem[1:, :] - dem[:-1, :]) / y_size_m
        )[forward]
        dz_dy[1:, :][forward] = dz_dy[:-1, :][forward]

    if cols > 2:
        central = valid[:, :-2] & valid[:, 1:-1] & valid[:, 2:]
        dz_dx[:, 1:-1][central] = (
            (dem[:, 2:] - dem[:, :-2]) / (2 * x_size_m)
        )[central]
    if rows > 2:
        central = valid[:-2, :] & valid[1:-1, :] & valid[2:, :]
        dz_dy[1:-1, :][central] = (
            (dem[2:, :] - dem[:-2, :]) / (2 * y_size_m)
        )[central]

    gradient_valid = valid.copy()
    gradient_valid[:, 1:] &= valid[:, :-1]
    gradient_valid[:, :-1] &= valid[:, 1:]
    gradient_valid[1:, :] &= valid[:-1, :]
    gradient_valid[:-1, :] &= valid[1:, :]
    slope_deg = np.degrees(np.arctan(np.hypot(dz_dx, dz_dy))).astype("float32")
    slope_deg[~gradient_valid] = np.nan
    return slope_deg


def calculate_roughness(dem: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Return local 5x5 elevation standard deviation in meters."""
    padded_dem = np.pad(dem.astype("float64"), 2, mode="edge")
    padded_valid = np.pad(valid, 2, mode="constant", constant_values=False)
    values = sliding_window_view(padded_dem, (5, 5))
    masks = sliding_window_view(padded_valid, (5, 5))
    count = masks.sum(axis=(2, 3))
    masked_values = np.where(masks, values, np.nan)
    roughness = np.nanstd(masked_values, axis=(2, 3)).astype("float32")
    roughness[(count < 25) | ~valid] = np.nan
    return roughness


def build_hazard_mask(
    slope_deg: np.ndarray,
    roughness: np.ndarray,
    max_slope_deg: float,
    max_roughness_m: float,
) -> np.ndarray:
    """Build the sole routing/display hazard mask, treating invalid cells as blocked."""
    valid = (
        np.isfinite(slope_deg)
        & (slope_deg != -9999)
        & np.isfinite(roughness)
        & (roughness != -9999)
    )
    return (
        ~valid
        | (slope_deg > max_slope_deg)
        | (roughness > max_roughness_m)
    )


def rgba_from_scalar(values: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Scale each scalar image from its own valid min/max with transparency."""
    rgba = np.zeros((*values.shape, 4), dtype=np.uint8)
    good = valid & np.isfinite(values)
    if not np.any(good):
        return rgba
    minimum = float(values[good].min())
    maximum = float(values[good].max())
    if maximum == minimum:
        scaled = np.full(values.shape, 127, dtype=np.uint8)
    else:
        scaled = np.clip((values - minimum) / (maximum - minimum) * 255, 0, 255)
        scaled = np.nan_to_num(scaled, nan=0).astype(np.uint8)
    rgba[..., :3] = scaled[..., None]
    rgba[..., 3] = np.where(good, 255, 0)
    return rgba


def write_png(path: Path, rgba: np.ndarray) -> None:
    Image.fromarray(rgba, mode="RGBA").save(path)


def export_imagery(
    path: Path,
    shape: tuple[int, int],
    transform,
    crs,
    output: Path,
) -> None:
    with rasterio.open(path) as source:
        image = np.full(shape, np.nan, dtype="float32")
        reproject(
            source=rasterio.band(source, 1),
            destination=image,
            src_transform=source.transform,
            src_crs=source.crs,
            src_nodata=source.nodata,
            dst_transform=transform,
            dst_crs=crs,
            dst_nodata=np.nan,
            resampling=rasterio.enums.Resampling.bilinear,
        )
        valid = np.isfinite(image)
    write_png(output, rgba_from_scalar(image, valid))


def export_hillshade(dem_path: Path, output: Path) -> None:
    environment = os.environ.copy()
    environment["GDAL_PAM_ENABLED"] = "NO"
    subprocess.run(
        [
            "gdaldem",
            "hillshade",
            "-q",
            "-s",
            "59157",
            "-compute_edges",
            "-of",
            "PNG",
            str(dem_path),
            str(output),
        ],
        check=True,
        env=environment,
    )


def process_site(site: str) -> None:
    config = site_config(site)
    output = site_output_dir(site)
    with rasterio.open(config["dem_path"]) as source:
        dem = source.read(1).astype("float32")
        nodata = source.nodata
        valid = np.isfinite(dem)
        if nodata is not None:
            valid &= dem != nodata
        x_size_m, y_size_m = cell_size_meters(source)
        profile = source.profile.copy()
        transform = source.transform
        crs = source.crs

    if not np.any(valid):
        raise ValueError(f"{site} DEM contains no valid cells")
    slope_deg = calculate_slope(dem, x_size_m, y_size_m, valid)
    roughness = calculate_roughness(dem, valid)
    slope_valid = np.isfinite(slope_deg)
    roughness_valid = np.isfinite(roughness)
    hazard_mask = build_hazard_mask(
        slope_deg,
        roughness,
        MAX_WALKABLE_SLOPE_DEG,
        MAX_ROUGHNESS_M,
    )
    slope_output = np.where(slope_valid, slope_deg, -9999).astype("float32")
    roughness_output = np.where(roughness_valid, roughness, -9999).astype("float32")

    raster_profile = profile.copy()
    raster_profile.update(count=1, dtype="float32", nodata=-9999)
    for name, values in (("slope", slope_output), ("roughness", roughness_output)):
        with rasterio.open(output / f"{name}.tif", "w", **raster_profile) as target:
            target.write(values, 1)
            target.update_tags(
                DATA_STATUS="REAL - derived from supplied NASA DEM",
                SOURCE_PROVENANCE=config["provenance"],
                CELL_SIZE_X_M=f"{x_size_m:.3f}",
                CELL_SIZE_Y_M=f"{y_size_m:.3f}",
            )
    hazard_profile = profile.copy()
    hazard_profile.update(count=1, dtype="uint8", nodata=None)
    with rasterio.open(output / "hazard.tif", "w", **hazard_profile) as target:
        target.write(hazard_mask.astype("uint8"), 1)
        target.update_tags(
            DATA_STATUS="REAL - derived from supplied NASA DEM",
            SOURCE_PROVENANCE=config["provenance"],
            HAZARD_ENCODING="0=clear, 1=slope_or_roughness_or_nodata_hazard",
            CELL_SIZE_X_M=f"{x_size_m:.6f}",
            CELL_SIZE_Y_M=f"{y_size_m:.6f}",
        )

    elevation_valid = valid & np.isfinite(dem)
    write_png(output / "elevation.png", rgba_from_scalar(dem, elevation_valid))
    write_png(output / "slope.png", rgba_from_scalar(slope_deg, slope_valid))
    hazard_rgba = np.zeros((*hazard_mask.shape, 4), dtype=np.uint8)
    hazard_rgba[hazard_mask, :3] = (239, 68, 68)
    hazard_rgba[hazard_mask, 3] = 220
    write_png(output / "hazard.png", hazard_rgba)
    export_imagery(
        config["imagery_path"],
        dem.shape,
        transform,
        crs,
        output / "imagery.png",
    )
    export_hillshade(config["dem_path"], output / "hillshade.png")

    print(
        f"{site}: cell size x={x_size_m:.3f} m, y={y_size_m:.3f} m; "
        f"hazard cells={hazard_mask.sum()} "
        f"({100 * hazard_mask.mean():.2f}% of grid)"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", choices=sorted(SITES), required=True)
    args = parser.parse_args()
    process_site(args.site)


if __name__ == "__main__":
    main()
