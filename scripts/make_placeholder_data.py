"""Generate a small, clearly labeled DEM for local pipeline development."""

from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_bounds

from config import AOI_BOUNDS


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "data" / "processed" / "dem.tif"
ROWS = 64
COLS = 64


def make_dem() -> np.ndarray:
    """Return a smooth synthetic elevation surface, not NASA data."""
    y, x = np.mgrid[0:ROWS, 0:COLS]
    ridge = 650.0 * np.exp(-(((x - 34.0) / 2.2) ** 2 + ((y - 32.0) / 12.0) ** 2))
    undulation = 12.0 * np.sin(x / 8.0) * np.cos(y / 11.0)
    return (1000.0 + ridge + undulation).astype("float32")


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    bounds = AOI_BOUNDS
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
    main()
