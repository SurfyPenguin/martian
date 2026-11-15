# Moon mode verification

The Moon source audit is in `docs/MOON_DATA_NOTES.md`. Processors and verifiers
use bounded or decimated reads; no full source raster is loaded. Routing uses
the configured two-cell safety margin, 15-degree slope limit, 15 m roughness
limit, 3 km/h walking-speed assumption, and four-hour EVA assumption. These
are assumptions, not validated mission limits.

The roughness backdrop is a 304 x 304 PNG (198,357 bytes) scaled with a
2nd-to-98th percentile clip. Its valid source overview pixels are opaque; the
Python checker also verifies that invalid pixels become transparent.

## site_01: Connecting Ridge

| Measurement | Result |
|---|---:|
| Routing cell size | 10 m |
| Elevation min / max / standard deviation | 1108.242 / 1959.143 / 183.840 m |
| DEM NoData cells | 0 |
| Supplied-vs-derived slope mean absolute difference | 0.4110 degrees |
| Source 5 m pixels with recorded LOLA returns | 8.3265% |
| Hazard fraction | 39.93% |
| Largest passable component | 42.44% |
| Chokepoints at configured margin | 1 |
| Automatic placeholder round trip | 8.473 km / 2.824 h |
| Automatic return margin | 1.176 h |

The successful processor run peaked at 259,536 KB RSS. The Python verifier
peaked at 175,832 KB; the JavaScript verifier peaked at 158,856 KB.

Both verifiers confirmed that the three placeholder targets lie in reachable
terrain and that a straight line between two targets crosses hazards. All four
automatic route legs and 20 random three-checkpoint sets per verifier had zero
hazard cells. Minimum automatic-route clearance was 22.4 m (28.3 m on the
return leg). The synthetic diagonal-gap test rejected corner cutting.

| Edge case | Python result | JavaScript result |
|---|---|---|
| Checkpoint on hazard | Snapped 56.6 m to free cell (4, 4) | Snapped 56.6 m to free cell (4, 4) |
| Checkpoint inside safety margin | Snapped 28.3 m to free cell (4, 4) | Snapped 28.3 m to free cell (4, 4) |
| Disconnected pocket | No walkable route | Leg marked unreachable (`NO SAFE PATH`) |
| Over-limit round trip | 16.395 km / 5.465 h, over the four-hour assumption | 16.395 km / 5.465 h, over the four-hour assumption |

### A* and Dijkstra parity

Each implementation ran 20 random endpoint pairs. All A* costs matched
Dijkstra exactly in the printed precision; maximum relative difference was
0.000%. Timing and explored-cell counts are means over those 20 pairs.

| Implementation | A* ms | Dijkstra ms | A* explored | Dijkstra explored |
|---|---:|---:|---:|---:|
| Python | 336.10 | 676.77 | 19,241 | 44,223 |
| JavaScript | 21.46 | 40.47 | 23,020 | 53,042 |

### Browser checks

The Moon selector loaded the site, four route legs, all 13 named-region
outlines, the roughness backdrop, and the LOLA support layer. A manual Moon
checkpoint recalculated the route. Switching back to Mars restored its
imagery and route panel. The Moon backdrop path was corrected after a 404 was
found; a subsequent Mars/Moon switch produced no failed network requests or
console errors.

## Remaining sites

## site_04: unmatched supplied raster

The GeoJSON has no matching site_04 region, so the planning window is centered
on the supplied raster midpoint and is not given a named-region identity.

| Measurement | Result |
|---|---:|
| Routing cell size | 10 m |
| Elevation min / max / standard deviation | -831.536 / 1738.573 / 779.070 m |
| DEM NoData cells | 0 |
| Supplied-vs-derived slope mean absolute difference | 0.5366 degrees |
| Source 5 m pixels with recorded LOLA returns | 8.1837% |
| Hazard fraction | 86.20% |
| Largest passable component | 7.27% |
| Chokepoints at configured margin | 1 |
| Automatic placeholder round trip | 8.748 km / 2.916 h |
| Automatic return margin | 1.084 h |

This site is highly hazardous under the unchanged configured thresholds.
Its small largest passable component is reported as measured; the thresholds
were not relaxed. The four automatic route legs and 20 random checkpoint sets
per verifier had zero hazard cells. Minimum automatic-route clearance was
22.4 m. Straight target-to-target lines cross hazards, while the auto route
stays clear.

| Edge case | Python result | JavaScript result |
|---|---|---|
| Checkpoint on hazard | Snapped 98.5 m to free cell (9, 4) | Snapped 98.5 m to free cell (9, 4) |
| Checkpoint inside safety margin | Snapped 70.7 m to free cell (7, 7) | Snapped 70.7 m to free cell (7, 7) |
| Disconnected pocket | No walkable route | Leg marked unreachable (`NO SAFE PATH`) |
| Over-limit round trip | 17.156 km / 5.719 h, over the four-hour assumption | 17.156 km / 5.719 h, over the four-hour assumption |

Each implementation compared A* and Dijkstra on 20 random pairs. All costs
matched exactly at the printed precision; maximum relative difference was
0.000%. Timing and explored-cell counts are means.

| Implementation | A* ms | Dijkstra ms | A* explored | Dijkstra explored |
|---|---:|---:|---:|---:|
| Python | 69.69 | 75.33 | 5,496 | 7,805 |
| JavaScript | 6.17 | 7.18 | 6,947 | 10,532 |

Processing peaked at 259,280 KB RSS. The Python verifier peaked at
149,872 KB; the JavaScript verifier peaked at 115,708 KB. All site output
files are below 1 MB.

## site_07: Peak Near Shakleton

The name is preserved exactly as supplied in the GeoJSON.

| Measurement | Result |
|---|---:|
| Routing cell size | 10 m |
| Elevation min / max / standard deviation | 739.848 / 1648.577 / 172.855 m |
| DEM NoData cells | 0 |
| Supplied-vs-derived slope mean absolute difference | 0.3571 degrees |
| Source 5 m pixels with recorded LOLA returns | 6.5342% |
| Hazard fraction | 25.56% |
| Largest passable component | 63.02% |
| Chokepoints at configured margin | 0 |
| Automatic placeholder round trip | 7.436 km / 2.479 h |
| Automatic return margin | 1.521 h |

Both verifiers confirmed that straight target-to-target lines cross hazards.
All four automatic route legs and 20 random checkpoint sets per verifier had
zero hazard cells. Minimum automatic-route clearance ranged from 22.4 m to
56.6 m.

| Edge case | Python result | JavaScript result |
|---|---|---|
| Checkpoint on hazard | Snapped 56.6 m to free cell (4, 4) | Snapped 56.6 m to free cell (4, 4) |
| Checkpoint inside safety margin | Snapped 28.3 m to free cell (4, 4) | Snapped 28.3 m to free cell (4, 4) |
| Disconnected pocket | No walkable route | Leg marked unreachable (`NO SAFE PATH`) |
| Over-limit round trip | 14.763 km / 4.921 h, over the four-hour assumption | 14.763 km / 4.921 h, over the four-hour assumption |

Each implementation compared A* and Dijkstra on 20 random pairs. All costs
matched exactly at the printed precision; maximum relative difference was
0.000%. Timing and explored-cell counts are means.

| Implementation | A* ms | Dijkstra ms | A* explored | Dijkstra explored |
|---|---:|---:|---:|---:|
| Python | 580.91 | 1125.81 | 39,380 | 85,414 |
| JavaScript | 26.44 | 53.34 | 33,428 | 83,329 |

Processing peaked at 260,996 KB RSS. The Python verifier peaked at
173,112 KB; the JavaScript verifier peaked at 146,204 KB. All site output
files are below 1 MB.

## sl3: Connecting Ridge Extension

| Measurement | Result |
|---|---:|
| Routing cell size | 10 m |
| Elevation min / max / standard deviation | 706.010 / 1543.718 / 196.842 m |
| DEM NoData cells | 0 |
| Supplied-vs-derived slope mean absolute difference | 0.3218 degrees |
| Source 5 m pixels with recorded LOLA returns | 2.9643% |
| Hazard fraction | 14.88% |
| Largest passable component | 67.40% |
| Chokepoints at configured margin | 0 |
| Automatic placeholder round trip | 9.236 km / 3.079 h |
| Automatic return margin | 0.921 h |

Both verifiers confirmed that straight target-to-target lines cross hazards.
All four automatic route legs and 20 random checkpoint sets per verifier had
zero hazard cells. Minimum automatic-route clearance was 22.4 m.

| Edge case | Python result | JavaScript result |
|---|---|---|
| Checkpoint on hazard | Snapped 458.8 m to free cell (13, 44) | Snapped 458.8 m to free cell (13, 44) |
| Checkpoint inside safety margin | Snapped 376.4 m to free cell (13, 44) | Snapped 376.4 m to free cell (13, 44) |
| Disconnected pocket | No walkable route | Leg marked unreachable (`NO SAFE PATH`) |
| Over-limit round trip | 18.356 km / 6.119 h, over the four-hour assumption | 18.356 km / 6.119 h, over the four-hour assumption |

Each implementation compared A* and Dijkstra on 20 random pairs. All costs
matched exactly at the printed precision; maximum relative difference was
0.000%. Timing and explored-cell counts are means.

| Implementation | A* ms | Dijkstra ms | A* explored | Dijkstra explored |
|---|---:|---:|---:|---:|
| Python | 449.79 | 935.00 | 26,322 | 62,302 |
| JavaScript | 42.54 | 68.00 | 45,153 | 89,689 |

Processing peaked at 258,652 KB RSS. The Python verifier peaked at
181,680 KB; the JavaScript verifier peaked at 153,844 KB. All site output
files are below 1 MB.

## Final verification (2026-11-15)

All checks re-ran on the completed branch under `/usr/bin/time -v`. The four
Python verifier peaks were site_01 178,048 KB, site_04 149,912 KB, site_07
185,096 KB, and sl3 185,056 KB RSS; every result matched the per-site tables
above. The disconnected-pocket cases now exercise actual disconnected
passable pockets located on each site's route grid instead of a synthetic
20 x 20 grid; each correctly reported `NO SAFE PATH`.

The Mars regression passed: `check_hazards.py`, `check_hazards.js`,
`check_algorithms.js` (80 A*/Dijkstra pairs within 0.1%), and
`check_site_edge_cases.py` all exited zero.

A headless Chrome check drove the real page through the body selector:
Mars default, one restored auto plan on each of the four Mars sites, all four
Moon sites with restored auto plans, and a switch back to Mars site1. The Moon
sites showed the hillshade/slope/hazard/support layers, hid the Mars-only CTX
imagery row, and labeled the dose control "Lunar dose". No console errors,
page errors, or failed network requests appeared in either mode.
