"""Create slope and walkability rasters from a DEM."""

import numpy as np
import rasterio

from config import DEM_PATH, HAZARD_PATH, MAX_WALKABLE_SLOPE_DEG, SLOPE_PATH


PLACEHOLDER_TAGS = {
    "DATA_STATUS": "PLACEHOLDER - derived from synthetic DEM, not NASA data",
    "DESCRIPTION": "Slope and hazard outputs for local pipeline development",
}


def calculate_slope(dem: np.ndarray, x_size: float, y_size: float) -> np.ndarray:
    """Calculate slope angle in degrees using the DEM's cell dimensions."""
    dz_dy, dz_dx = np.gradient(dem, y_size, x_size)
    return np.degrees(np.arctan(np.hypot(dz_dx, dz_dy))).astype("float32")


def main() -> None:
    with rasterio.open(DEM_PATH) as source:
        dem = source.read(1).astype("float32")
        x_size, y_size = source.res
        nodata = source.nodata
        valid = np.isfinite(dem)
        if nodata is not None:
            valid &= dem != nodata
        if not np.any(valid):
            raise ValueError(f"DEM contains no valid cells: {DEM_PATH}")

        slope = calculate_slope(dem, abs(x_size), abs(y_size))
        slope_nodata = -9999.0
        slope[~valid] = slope_nodata
        hazard = np.where(valid, slope > MAX_WALKABLE_SLOPE_DEG, 255).astype(
            "uint8"
        )
        hazard[~valid] = 255

        profile = source.profile.copy()
        profile.update(count=1, dtype="float32", nodata=slope_nodata)
        with rasterio.open(SLOPE_PATH, "w", **profile) as output:
            output.write(slope, 1)
            output.update_tags(**PLACEHOLDER_TAGS)

        hazard_profile = source.profile.copy()
        hazard_profile.update(count=1, dtype="uint8", nodata=255)
        with rasterio.open(HAZARD_PATH, "w", **hazard_profile) as output:
            output.write(hazard, 1)
            output.update_tags(
                **PLACEHOLDER_TAGS,
                HAZARD_ENCODING="0=walkable, 1=over max slope, 255=nodata",
            )

    valid_slope = slope[valid]
    print(
        "Slope degrees: "
        f"min={valid_slope.min():.3f}, "
        f"max={valid_slope.max():.3f}, "
        f"mean={valid_slope.mean():.3f}"
    )


if __name__ == "__main__":
    main()
