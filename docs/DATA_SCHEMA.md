# Real input data schema

These files are the clipped real inputs used by the site pipeline. The site coordinates in `scripts/config.py` remain explicitly labeled placeholders until mission points are supplied. The supplied files are identified as NASA-provided inputs, but product IDs and acquisition dates were not included.

| File | Shape | Bands | Dtype | CRS | NoData | Bounds (left, bottom, right, top) | Resolution (x, y) | Size |
|---|---:|---:|---|---|---:|---|---|---:|
| `data/processed/site1_dem.tif` | 500 x 502 | 1 | float32 | `ESRI:104905` | `-3.4028230607370965e+38` | `(137.3837293189, -4.6294578194, 137.4685673189, -4.5449578194)` | `(0.000169, 0.000169)` | 704,696 bytes |
| `data/processed/site1_imagery.tif` | 1003 x 1006 | 1 | uint8 | `ESRI:104971` | `None` | `(137.3836794254, -4.6295525992, 137.4685385434, -4.5449465402)` | `(8.4353e-05, 8.4353e-05)` | 653,681 bytes |
| `data/processed/site2_dem.tif` | 501 x 502 | 1 | float32 | `ESRI:104905` | `-3.4028230607370965e+38` | `(137.3575967519, -4.8423651466, 137.4424347519, -4.7576961466)` | `(0.000169, 0.000169)` | 813,305 bytes |
| `data/processed/site2_imagery.tif` | 1004 x 1007 | 1 | uint8 | `ESRI:104971` | `None` | `(137.3575299954, -4.8423752182, 137.4424734664, -4.7576848062)` | `(8.4353e-05, 8.4353e-05)` | 778,473 bytes |

DEM values are elevation in meters. DEM NoData is treated as impassable; slope is never computed across invalid neighborhoods. Imagery is CTX single-band raster data and is resampled to each site's DEM grid for the browser overlay.

## Browser route-cost grids

`python scripts/route.py --site <site>` exports a browser-ready grid under
`web/data/<site>/` alongside the processed route products.

| File | Contents |
|---|---|
| `cost.json` | Site key, row/column dimensions, geographic bounds, x/y cell sizes in meters, encoding, impassable sentinel, and route assumptions from `scripts/config.py` |
| `cost.bin` | One little-endian Float32 cost per DEM cell, row-major, with exactly `rows * cols * 4` bytes |

Cells that fail the configured slope or roughness walkability limits, or have
invalid inputs, contain `-1` and are impassable. Other cells contain
`1 + (slope / max_slope)^slope_cost_power + (roughness / max_roughness) * roughness_cost_weight`.
Browser A* multiplies each destination cell's cost by the 8-neighbor distance,
using the x and y cell sizes from `cost.json`. This preserves the Python route
cost model. Manual checkpoints are kept in browser memory and are not written
back to these generated files.
