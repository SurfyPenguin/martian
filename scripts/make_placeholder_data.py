"""Generate the legacy synthetic DEM only when explicitly requested."""

import argparse
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_bounds

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "data" / "processed" / "dem.tif"
ROWS = 64
COLS = 64
# PLACEHOLDER bounds retained only for the explicit demo fallback.
PLACEHOLDER_BOUNDS = {
    "min_lon": 137.64,
    "min_lat": -4.684,
    "max_lon": 137.68,
    "max_lat": -4.60,
}


def make_dem() -> np.ndarray:
    """Return a varied synthetic elevation surface, not NASA data."""
    y, x = np.mgrid[0:ROWS, 0:COLS]
    ridge = 650.0 * np.exp(-(((x - 34.0) / 2.2) ** 2 + ((y - 32.0) / 12.0) ** 2))
    rolling_hills = (
        35.0 * np.sin(x / 6.0) * np.cos(y / 8.0)
        + 22.0 * np.sin((x + y) / 4.5)
        - 16.0 * np.cos((x - 2.0 * y) / 7.0)
    )
    crater = -70.0 * np.exp(-(((x - 13.0) / 8.0) ** 2 + ((y - 47.0) / 6.0) ** 2))
    terrace = 30.0 * np.exp(-(((x - 51.0) / 10.0) ** 2 + ((y - 13.0) / 14.0) ** 2))
    fine_texture = 5.0 * np.sin(x * 1.4 + y * 0.7)
    return (1000.0 + ridge + rolling_hills + crater + terrace + fine_texture).astype(
        "float32"
    )


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    bounds = PLACEHOLDER_BOUNDS
    transform = from_bounds(
        bounds["min_lon"],
        bounds["min_lat"],
        bounds["max_lon"],
        bounds["max_lat"],
        COLS,
        ROWS,
    )
    dem = make_dem()

    with rasterio.open(
        OUTPUT_PATH,
        "w",
        driver="GTiff",
        height=ROWS,
        width=COLS,
        count=1,
        dtype=dem.dtype,
        transform=transform,
        nodata=-9999.0,
    ) as dataset:
        dataset.write(dem, 1)
        dataset.update_tags(
            DATA_STATUS="PLACEHOLDER - synthetic DEM, not NASA data",
            DESCRIPTION="Synthetic elevation surface for local pipeline development",
            COORDINATE_CONVENTION=(
                "Placeholder Mars geographic coordinates: planetocentric latitude, "
                "east-positive longitude"
            ),
            CRS_STATUS="UNSPECIFIED - no Mars CRS assigned",
        )

    print(f"Wrote placeholder DEM: {OUTPUT_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--placeholder",
        action="store_true",
        help=" opt into generating the legacy synthetic DEM",
    )
    args = parser.parse_args()
    if not args.placeholder:
        parser.error("synthetic generation is disabled; pass --placeholder explicitly")
    main()
