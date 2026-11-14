"""Build slope, roughness, hazard, and browser rasters for one real site."""

import argparse
import math
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from numpy.lib.stride_tricks import sliding_window_view

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


def read_dem(path: Path) -> tuple[np.ndarray, np.ndarray, float]:
    with rasterio.open(path) as source:
        dem = source.read(1).astype("float32")
        nodata = source.nodata
        valid = np.isfinite(dem)
        if nodata is not None:
            valid &= dem != nodata
        return dem, valid, nodata


def calculate_slope(
    dem: np.ndarray,
    x_size_m: float,
    y_size_m: float,
    valid: np.ndarray,
) -> np.ndarray:
    """Calculate slope only where the four cardinal neighbors are valid."""
    filled = np.where(valid, dem, 0.0)
    dz_dy, dz_dx = np.gradient(filled, y_size_m, x_size_m)
    slope = np.degrees(np.arctan(np.hypot(dz_dx, dz_dy))).astype("float32")
    gradient_valid = valid.copy()
    gradient_valid[:, 1:] &= valid[:, :-1]
    gradient_valid[:, :-1] &= valid[:, 1:]
    gradient_valid[1:, :] &= valid[:-1, :]
    gradient_valid[:-1, :] &= valid[1:, :]
    slope[~gradient_valid] = np.nan
    return slope


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


def export_imagery(path: Path, shape: tuple[int, int], output: Path) -> None:
    with rasterio.open(path) as source:
        image = source.read(
            1,
            out_shape=shape,
            resampling=rasterio.enums.Resampling.bilinear,
        ).astype("float32")
        valid = np.isfinite(image)
    write_png(output, rgba_from_scalar(image, valid))


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
        bounds = source.bounds

    if not np.any(valid):
        raise ValueError(f"{site} DEM contains no valid cells")
    slope = calculate_slope(dem, x_size_m, y_size_m, valid)
    roughness = calculate_roughness(dem, valid)
    slope_valid = np.isfinite(slope)
    roughness_valid = np.isfinite(roughness)
    hazard = (
        ~slope_valid
        | ~roughness_valid
        | (slope > MAX_WALKABLE_SLOPE_DEG)
        | (roughness > MAX_ROUGHNESS_M)
    )
    slope_output = np.where(slope_valid, slope, -9999).astype("float32")
    roughness_output = np.where(roughness_valid, roughness, -9999).astype("float32")

    raster_profile = profile.copy()
    raster_profile.update(count=1, dtype="float32", nodata=-9999)
    for name, values in (("slope", slope_output), ("roughness", roughness_output)):
        with rasterio.open(output / f"{name}.tif", "w", **raster_profile) as target:
            target.write(values, 1)
            target.update_tags(
                DATA_STATUS="REAL - derived from supplied NASA DEM",
                CELL_SIZE_X_M=f"{x_size_m:.3f}",
                CELL_SIZE_Y_M=f"{y_size_m:.3f}",
            )
    hazard_profile = profile.copy()
    hazard_profile.update(count=1, dtype="uint8", nodata=255)
    with rasterio.open(output / "hazard.tif", "w", **hazard_profile) as target:
        target.write(np.where(hazard, 1, 0).astype("uint8"), 1)
        target.update_tags(
            DATA_STATUS="REAL - derived from supplied NASA DEM",
            HAZARD_ENCODING="0=walkable, 1=slope_or_roughness_hazard, 255=nodata",
        )

    elevation_valid = valid & np.isfinite(dem)
    write_png(output / "elevation.png", rgba_from_scalar(dem, elevation_valid))
    write_png(output / "slope.png", rgba_from_scalar(slope, slope_valid))
    hazard_rgba = np.zeros((*hazard.shape, 4), dtype=np.uint8)
    display_hazard = valid & slope_valid & roughness_valid & hazard
    hazard_rgba[display_hazard, :3] = (239, 68, 68)
    hazard_rgba[display_hazard, 3] = 220
    write_png(output / "hazard.png", hazard_rgba)
    export_imagery(config["imagery_path"], dem.shape, output / "imagery.png")

    above_slope = valid & (slope > MAX_WALKABLE_SLOPE_DEG)
    print(
        f"{site}: cell size x={x_size_m:.3f} m, y={y_size_m:.3f} m; "
        f"slope>{MAX_WALKABLE_SLOPE_DEG:g}° in "
        f"{100 * above_slope.sum() / valid.sum():.2f}% of valid cells; "
        f"hazard cells={hazard.sum()}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", choices=sorted(SITES), required=True)
    args = parser.parse_args()
    process_site(args.site)


if __name__ == "__main__":
    main()
