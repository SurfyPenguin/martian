import json
import sys
import unittest
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from config import (  # noqa: E402
    MAX_ROUGHNESS_M,
    MAX_WALKABLE_SLOPE_DEG,
    SITES,
)
from slope import calculate_slope, cell_size_meters  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]


class RealPipelineTests(unittest.TestCase):
    def test_slope_masks_invalid_neighborhoods_without_filling_nodata(self):
        dem = np.arange(25, dtype="float32").reshape(5, 5)
        valid = np.ones((5, 5), dtype=bool)
        valid[2, 2] = False

        slope_deg = calculate_slope(dem, 1.0, 1.0, valid)

        self.assertTrue(np.isnan(slope_deg[2, 2]))
        self.assertTrue(np.isnan(slope_deg[2, 1]))
        self.assertTrue(np.isnan(slope_deg[1, 2]))
        self.assertTrue(np.isfinite(slope_deg[0, 0]))

    def test_site_cell_sizes_are_about_ten_meters(self):
        for site, site_config in SITES.items():
            with self.subTest(site=site):
                with rasterio.open(site_config["dem_path"]) as source:
                    x_size_m, y_size_m = cell_size_meters(source)
                self.assertAlmostEqual(x_size_m, 10.0, delta=0.1)
                self.assertAlmostEqual(y_size_m, 10.0, delta=0.1)

    def test_routes_only_use_walkable_cells(self):
        for site in SITES:
            with self.subTest(site=site):
                output = ROOT / "data" / "processed" / site
                grid = json.loads((output / "grid.json").read_text())
                route = np.asarray(grid["route_pixels"])
                with rasterio.open(output / "hazard.tif") as source:
                    hazard = source.read(1)
                with rasterio.open(output / "slope.tif") as source:
                    slope_deg = source.read(1)
                with rasterio.open(output / "roughness.tif") as source:
                    roughness = source.read(1)

                rows, cols = route[:, 0], route[:, 1]
                self.assertTrue(np.all(hazard[rows, cols] == 0))
                self.assertTrue(np.all(slope_deg[rows, cols] <= MAX_WALKABLE_SLOPE_DEG))
                self.assertTrue(np.all(roughness[rows, cols] <= MAX_ROUGHNESS_M))


if __name__ == "__main__":
    unittest.main()
