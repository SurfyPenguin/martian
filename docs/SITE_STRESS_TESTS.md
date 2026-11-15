# Fixed site-window stress tests

The two requested windows were clipped from `data/raw/gale_dem_smg_1m.tif` and
`data/raw/gale_ctx_blockadj_dd.tif` using only `gdal_translate -projwin -tr
0.000169 0.000169 -r average`. CTX coverage was checked with `gdalinfo -nomd`;
no statistics were requested on either large source. The raw inputs were never
loaded into Python or scanned. Final site clips are 502 x 501 cells at about
10 m per pixel.

The requested WNES bounds and centers were retained. Both windows fall inside
the DEM extent (137.122471-137.729813 E, -4.925474 to -4.248963) and CTX extent
(135.184259-139.241301 E, -6.573299 to -2.807781). The site4 southern bound is
-4.9223, about 188 m north of the DEM edge. No NoData occurred in either
resampled DEM clip, both CTX clips had full coverage, and no site shift was
needed. Pixel-aligned raster bounds extend only a few meters beyond the
requested east/south values.

All thresholds are unchanged: slope over 15 degrees, 5 x 5 roughness over 15 m,
two-cell routing margin, 3 km/h walking speed, and four-hour EVA assumption.
These are planning assumptions, not validated mission limits. The points below
are PLACEHOLDERS, chosen in each window's largest connected passable component;
they are not mission-validated.

## Measured site properties

| Site | Requested center (lat, lon) | Raster bounds (W, N, E, S) | DEM min / max / std (m) | DEM NoData | CTX source min / max / spread; scaled output | CTX NoData | Cell size (x, y) m | Hazard | Passable components | Largest passable component | Chokepoints |
|---|---|---|---:|---:|---|---:|---|---:|---:|---:|---:|
| site3, Rough terrain box | -4.70, 137.38 | 137.337600, -4.657700, 137.422438, -4.742369 | -4482.600 / -3936.100 / 125.917 | 0 | 6 / 188 / 182; 0-255 | 0 | 9.964 x 9.998 | 6.864% | 112 | 82.591% | 1 |
| site4, Dune-edge box | -4.88, 137.42 | 137.377600, -4.837700, 137.462438, -4.922369 | -3322.338 / -2197.732 / 239.407 | 0 | 10 / 249 / 239; 0-255 | 0 | 9.961 x 9.998 | 47.469% | 1,381 | 4.712% | 0 |

CTX source ranges are measured on the small resampled site clips before the
per-site linear stretch. The committed 8-bit imagery uses each clip's own
minimum and maximum. The smallest measured clear components identify site4 as
the visibly fragmented stress case; do not lower a threshold to improve its
metrics or route.

Previews are side-by-side, scaled CTX and GDAL hillshade (`gdaldem hillshade
-s 59157`), and each is under 300 KB:

- [site3 preview](site_previews/site3.png), 158,072 bytes
- [site4 preview](site_previews/site4.png), 182,670 bytes

## Route and algorithm checks

`python scripts/check_hazards.py` and `node scripts/check_hazards.js` both
checked every route cell in the auto plan and 20 random three-checkpoint sets
per site, for all four configured sites. Both reported zero hazard or margin
cells crossed. The new sites' automatic routes had 28.2 m minimum clearance
(site3) and 22.3 m (site4). The browser check also verified that the exported
overlay, binary hazard grid, and browser cost grid use the same mask.

The following A* / Dijkstra comparison used 20 random reachable pairs per site.
The maximum cost difference was 0.0000% in each row.

| Site | Pairs | A* average (ms) | Dijkstra average (ms) | A* cells explored | Dijkstra cells explored | Maximum cost difference |
|---|---:|---:|---:|---:|---:|---:|
| site3 | 20 | 57.73 | 95.08 | 52,820 | 115,310 | 0.0000% |
| site4 | 20 | 5.18 | 5.66 | 4,127 | 5,753 | 0.0000% |

The full four-site check compared 80 pairs and reported all costs equal within
0.1%.

## Required edge cases

| Site | Auto route | Hazard checkpoint | Inside safety margin | Disconnected pocket | Over-limit round trip |
|---|---|---|---|---|---|
| site3 | 20.545 km, 6.848 h, OVER EVA LIMIT | `(237, 240)` snapped 22.3 m to `(238, 242)` | `(239, 240)` snapped 10.0 m to `(239, 241)` | `(466, 495)` returned NO SAFE PATH; UI connector is red and dashed | 2 repeated out-and-back legs: 14.350 km, 4.783 h, OVER |
| site4 | 10.018 km, 3.339 h, WITHIN EVA LIMIT | `(86, 74)` snapped 22.3 m to `(87, 76)` | `(88, 74)` snapped 10.0 m to `(88, 73)` | `(287, 427)` returned NO SAFE PATH; UI connector is red and dashed | 3 repeated out-and-back legs: 13.531 km, 4.510 h, OVER |

For both sites, habitat and all three target placeholders are in the largest
passable component, and a straight line between neighboring targets crosses
true hazard cells. The over-limit stress sequence deliberately repeats a safe
out-and-back checkpoint leg for site4 because its auto plan is within the limit.
Neither test changed route assumptions.

A headless browser switched through site3, site4, and site1: descriptors and
safety summaries changed after fly-to completion; the slope/roughness
limitation note was visible only for site3 and site4. A disconnected site4
checkpoint produced `NO SAFE PATH` and two rendered red dashed legs; no browser
console errors were observed.

## Memory and output sizes

Every raster/GDAL processing command and the route and verification runs were
measured with `/usr/bin/time -v`. The site3 DEM clip's first trial with the
default GDAL cache peaked at 484,880 KB RSS; it was rerun for the committed
output with `GDAL_CACHEMAX=64`, peaking at 155,088 KB. No source-sized array was
loaded. The maximum final verification-process RSS was 296,728 KB (about
290 MiB); the largest Python array used by the checks is limited to the
501 x 502 site grid.

| Operation | Peak RSS (KB) |
|---|---:|
| Final site3 DEM clip, 64 MB GDAL cache | 155,088 |
| Final site4 DEM clip, 64 MB GDAL cache | 156,612 |
| Site3 / site4 slope and hillshade pipeline | 225,596 / 226,972 |
| Site3 / site4 route exports | 186,904 / 152,276 |
| Python hazard checks, all sites | 152,244 |
| Browser hazard checks, all sites | 296,728 |
| A* / Dijkstra checks, all sites | 201,028 |
| Site endpoint edge-case checks | 167,316 |

No generated output exceeds 5 MB. Files above 1 MB (decimal) are:

- `data/processed/site3_dem.tif` and `data/processed/site4_dem.tif`: 1,007,295 bytes each
- `data/processed/site3/slope.tif`, `data/processed/site3/roughness.tif`, `data/processed/site4/slope.tif`, and `data/processed/site4/roughness.tif`: 1,008,872 bytes each
- `web/data/site3/cost.bin`, `clearance-cells.bin`, and `clearance-meters.bin`: 1,006,008 bytes each
- `web/data/site4/cost.bin`, `clearance-cells.bin`, and `clearance-meters.bin`: 1,006,008 bytes each

No files from `data/raw/` or GDAL `.aux.xml` sidecars are included.
