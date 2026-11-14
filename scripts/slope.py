"""Create slope and walkability rasters from a DEM."""

import math
import numpy as np
import rasterio

if __package__:
    from .config import (
        DEM_PATH,
        HAZARD_PATH,
        MARS_RADIUS_KM,
        MAX_WALKABLE_SLOPE_DEG,
        SLOPE_PATH,
    )
else:
    from config import (
        DEM_PATH,
        HAZARD_PATH,
        MARS_RADIUS_KM,
        MAX_WALKABLE_SLOPE_DEG,
        SLOPE_PATH,
    )


PLACEHOLDER_TAGS = {
    "DATA_STATUS": "PLACEHOLDER - derived from synthetic DEM, not NASA data",
    "DESCRIPTION": "Slope and hazard outputs for local pipeline development",
}


def calculate_slope(
    dem: np.ndarray,
    x_size: float,
    y_size: float,
    valid_mask: np.ndarray | None = None,
) -> np.ndarray:
    """Calculate slope angle in degrees using the DEM's cell dimensions."""
    if valid_mask is None:
        valid_mask = np.isfinite(dem)
    if valid_mask.shape != dem.shape:
        raise ValueError("valid_mask must have the same shape as dem")

    filled_dem = np.where(valid_mask, dem, 0.0)
    dz_dy, dz_dx = np.gradient(filled_dem, y_size, x_size)
    slope_deg = np.degrees(np.arctan(np.hypot(dz_dx, dz_dy))).astype("float32")

    gradient_valid = valid_mask.copy()
    gradient_valid[:, 1:] &= valid_mask[:, :-1]
    gradient_valid[:, :-1] &= valid_mask[:, 1:]
    gradient_valid[1:, :] &= valid_mask[:-1, :]
    gradient_valid[:-1, :] &= valid_mask[1:, :]
    slope_deg[~gradient_valid] = np.nan
    return slope_deg


def cell_size_meters(source: rasterio.DatasetReader) -> tuple[float, float]:
    """Return x/y cell sizes in meters for projected or placeholder rasters."""
    x_size, y_size = source.res
    if source.crs is not None:
        return abs(x_size), abs(y_size)

    tags = source.tags()
    if tags.get("CRS_STATUS", "").startswith("UNSPECIFIED"):
        center_lat = math.radians((source.bounds.top + source.bounds.bottom) / 2)
        mars_radius_m = MARS_RADIUS_KM * 1000
        return (
            abs(x_size) * mars_radius_m * math.cos(center_lat) * math.pi / 180,
            abs(y_size) * mars_radius_m * math.pi / 180,
        )
    raise ValueError("DEM has no CRS or documented placeholder coordinate model")


def main() -> None:
    with rasterio.open(DEM_PATH) as source:
        dem = source.read(1).astype("float32")
        x_size, y_size = cell_size_meters(source)
        nodata = source.nodata
        valid = np.isfinite(dem)
        if nodata is not None:
            valid &= dem != nodata
        if not np.any(valid):
            raise ValueError(f"DEM contains no valid cells: {DEM_PATH}")

        slope_deg = calculate_slope(
            dem, abs(x_size), abs(y_size), valid_mask=valid
        )
        slope_nodata = -9999.0
        slope_valid = np.isfinite(slope_deg)
        slope_deg[~slope_valid] = slope_nodata
        hazard = np.where(
            slope_valid, slope_deg > MAX_WALKABLE_SLOPE_DEG, 255
        ).astype(
            "uint8"
        )
        hazard[~slope_valid] = 255

        profile = source.profile.copy()
        profile.update(count=1, dtype="float32", nodata=slope_nodata)
        with rasterio.open(SLOPE_PATH, "w", **profile) as output:
            output.write(slope_deg, 1)
            output.update_tags(**PLACEHOLDER_TAGS, CELL_SIZE_UNITS="meters")

        hazard_profile = source.profile.copy()
        hazard_profile.update(count=1, dtype="uint8", nodata=255)
        with rasterio.open(HAZARD_PATH, "w", **hazard_profile) as output:
            output.write(hazard, 1)
            output.update_tags(
                **PLACEHOLDER_TAGS,
                CELL_SIZE_UNITS="meters",
                HAZARD_ENCODING="0=walkable, 1=over max slope, 255=nodata",
            )

    valid_slope_deg = slope_deg[slope_valid]
    print(
        "Slope degrees: "
        f"min={valid_slope_deg.min():.3f}, "
        f"max={valid_slope_deg.max():.3f}, "
        f"mean={valid_slope_deg.mean():.3f}"
    )


if __name__ == "__main__":
    main()
