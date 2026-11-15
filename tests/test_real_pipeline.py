import json
import sys
import unittest
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from config import (  # noqa: E402
    SAFETY_MARGIN_CELLS,
    MAX_ROUGHNESS_M,
    MAX_WALKABLE_SLOPE_DEG,
    SITES,
)
from route import build_walkable_mask, distance_to_hazards  # noqa: E402
from slope import (  # noqa: E402
    build_hazard_mask,
    calculate_slope,
    cell_size_meters,
)


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

    def test_hazard_mask_blocks_thresholds_and_invalid_cells(self):
        slope_deg = np.array([[0, 16, np.nan]], dtype="float32")
        roughness = np.array([[0, 0, 0]], dtype="float32")
        mask = build_hazard_mask(slope_deg, roughness, 15, 15)
        np.testing.assert_array_equal(mask, [[False, True, True]])

    def test_hazard_raster_and_browser_costs_share_one_mask(self):
        for site in SITES:
            with self.subTest(site=site):
                output = ROOT / "data" / "processed" / site
                grid = json.loads((output / "grid.json").read_text())
                route = np.asarray(grid["route_pixels"])
                with rasterio.open(output / "hazard.tif") as source:
                    hazard = source.read(1) == 1
                    x_size_m, y_size_m = float(source.tags().get(
                        "CELL_SIZE_X_M", 0
                    )), float(source.tags().get("CELL_SIZE_Y_M", 0))
                with rasterio.open(output / "slope.tif") as source:
                    slope_deg = source.read(1)
                with rasterio.open(output / "roughness.tif") as source:
                    roughness = source.read(1)

                expected_hazard = build_hazard_mask(
                    slope_deg,
                    roughness,
                    MAX_WALKABLE_SLOPE_DEG,
                    MAX_ROUGHNESS_M,
                )
                np.testing.assert_array_equal(hazard, expected_hazard)
                self.assertGreaterEqual(x_size_m, 0)
                if not x_size_m:
                    x_size_m = grid["cell_size_m"]["x"]
                    y_size_m = grid["cell_size_m"]["y"]
                clearance_cells, clearance_meters = distance_to_hazards(
                    hazard,
                    x_size_m,
                    y_size_m,
                )
                costs = np.fromfile(
                    ROOT / "web" / "data" / site / "cost.bin",
                    dtype="<f4",
                ).reshape(hazard.shape)
                np.testing.assert_array_equal(np.isposinf(costs), hazard)
                walkable = build_walkable_mask(
                    costs,
                    clearance_cells,
                    SAFETY_MARGIN_CELLS,
                )
                rows, cols = route[:, 0], route[:, 1]
                self.assertTrue(np.all(~hazard[rows, cols]))
                self.assertTrue(np.all(walkable[rows, cols]))
                self.assertGreater(float(clearance_meters[rows, cols].min()), 0)


if __name__ == "__main__":
    unittest.main()
