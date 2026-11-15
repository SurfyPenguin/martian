# Martian Map: Project Plan

NASA Space Apps Challenge 2026, "Interplanetary Survival Guide: Martian Map".
Solo build. Full challenge text is in `docs/CHALLENGE.md`. Progress is tracked in
`docs/STATUS.md`.

## 1. Problem Statement

Astronauts planning a surface excursion need a hyperlocal view that combines
terrain, targets, route safety, and explicit mission assumptions. Mars mode
focuses on four clipped sites in Gale Crater. Moon mode demonstrates the same
planner on four south-polar raster windows, with distinct source limitations.
Context data is read only by decimated backdrop generation; site processing
uses bounded raster windows.

**Goal:** Build a layered, interactive EVA planning map that combines supplied
NASA data with derived hazard and route information. Lower-resolution
surrounding backdrops provide context only; routing is limited to the four
full-resolution sites for the selected body.

## 2. Solution: "Martian Map"

A tablet-style web app used to inspect a site, compare terrain layers, and plan
a route between placeholder science targets or manually added checkpoints.
The body selector switches between Mars and a separately configured Moon
south-pole demonstration mode.

**Locations:** Four windows in Gale Crater: the supplied **Gale crater floor**
and **Southern box**, plus fixed demo selections **Rough terrain box** and
**Dune-edge box** clipped from supplied NASA rasters. Product IDs and
acquisition dates were not included in this repository. Moon mode includes
the GeoJSON-named **Connecting Ridge**, **Peak Near Shakleton**, and
**Connecting Ridge Extension** regions, plus the unmatched `site_04` raster.
The `site_04` raster is not presented as a named region because its footprint
does not match the GeoJSON.

**Science objective:** Demonstrate route planning through three placeholder
science targets in each roughly 5 x 5 km site. Mission coordinates must replace
the placeholders before operational use. Moon mode is a planning prototype;
it does not integrate lunar imagery, illumination, temperature, or radiation.

**Scope (current MVP):**
- Four selectable sites defined in `scripts/config.py` and listed in the
  generated `web/data/sites.json` manifest
- Four Moon planning sites loaded from the generated
  `web/data/moon/body.json` manifest
- CTX imagery, elevation, slope, and slope/roughness hazard layers
- Moon hillshade, slope, hazard, and LOLA return-support layers over a
  lower-resolution LOLA roughness backdrop
- Live A*, Dijkstra, or Weighted A* routes between manually placed checkpoints
  and back to habitat, with selectable Fastest, Safer, and Alternate options
- Auto plan using three placeholder science targets
- Per-site checkpoint plans held in memory for the current page session
- Assumption-based dose and EVA safety summary

## 3. Data Layers

| Layer | Type | Source | MVP? |
|---|---|---|---|
| CTX imagery | Optical | Supplied CTX raster | Yes |
| Elevation | Topographic | Supplied DEM raster | Yes |
| Slope / roughness hazard | Derived topographic | Computed from the supplied DEM | Yes |
| Route / targets | Navigation | A* output and placeholder coordinates | Yes |
| Dose estimate | Safety planning | Labeled `scripts/config.py` assumption | Yes |
| Lunar roughness | Regional context | NASA LOLA roughness product, 1,000 m/pixel | Moon mode |
| Lunar elevation and slope | Site terrain | NASA-provided 5 m source rasters resampled to 10 m | Moon mode |
| LOLA return support | Data coverage | NASA LOLA count product, 5 m/pixel | Moon mode |

The supplied site rasters and lower-resolution context rasters are the real-data
inputs in the current pipeline. Their product IDs and acquisition dates are not
available in this repository.

## 4. Key Features

1. **Layer toggles** for all current datasets on one map.
2. **Hazard map** flagging slope and rough terrain.
3. **Route planner:** Browser-side A*, Dijkstra, or Weighted A* pathfinding over
   one exported hazard mask and terrain-cost grid, with hazard clearance,
   distance, time, dose, and unreachable-leg feedback. Alternative routes are
   checked against the same blocked cells before display.
4. **Safety sidebar:** assumption-based dose estimate, EVA time budget, and
   distance back to habitat.
5. **Checkpoint controls:** add checkpoints by clicking the map, drag to move,
   snap to nearby walkable cells, delete, undo, clear, or restore the automatic
   placeholder plan. The optional return leg and per-leg details update live.

## 5. Architecture

```text
data/raw/        source rasters (gitignored; windowed or decimated reads only)
scripts/
  config.py      site paths, coordinates, and labeled assumptions
  inspect_data.py  input schema inspection
  make_backdrop.py decimated context imagery/hillshade -> web/data/
  make_moon_site.py  bounded lunar site processing -> data/processed/moon/
  check_moon.py, check_moon.js  lunar projection and route verification
  slope.py       DEM -> meter-scaled slope/roughness -> shared hazard mask/PNG
  route.py       Python A* reference -> processed routes and browser cost/
                 clearance grids under web/data/<site>/
data/processed/  supplied inputs and per-site rasters, PNGs, route, stats, grid
  moon/          bounded lunar outputs, PNGs, grids, and measured statistics
web/
  index.html, app.js, geo.js, style.css   Leaflet app and shared projection
  data/         body manifests, low-resolution context images, bounds, and costs
```

**Pipeline:** inspect inputs -> generate decimated backdrop context -> compute
meter-scaled slope and 5x5 roughness -> export one shared hazard mask and
clearance grids -> run the Python reference route -> export aligned PNG,
GeoJSON, stats, route metadata, and browser cost grids -> Leaflet loads all
sites and route grids in the shared Mars map projection.

## 6. Assumptions

All adjustable assumptions live in `scripts/config.py` and are labeled in the
UI:

- Maximum walkable slope
- Maximum 5x5 elevation standard deviation
- Two-cell hazard clearance margin and soft clearance cost
- Walking speed
- EVA duration
- Dose rate used only for a planning estimate

These are not verified mission measurements or predictions.
Moon uses a separate `null` dose rate: no Mars radiation estimate is reused.
Moon walking speed, EVA duration, and slope limit are labeled assumptions.

## 7. Execution Plan

| Step | Task |
|---|---|
| 1 | Validate the supplied site rasters and coordinate placeholders |
| 2 | Process slope, roughness, hazard, and aligned browser overlays |
| 3 | Run A* routes for all four sites and inspect safety margins |
| 4 | Verify the Leaflet layers, site selector, safety sidebar, and checkpoints |
| 5 | Run the full pipeline and browser smoke checks |
| 6 | Process Moon sites with bounded reads and verify routing in Python and JavaScript |
| 7 | Prepare a demo and document remaining placeholders |

## 8. Definition of Done

- `python scripts/inspect_data.py` documents the supplied inputs
- `python scripts/slope.py --site <site>` and `python scripts/route.py --site <site>`
  produce outputs for site1 through site4
- `scripts/route.py` writes browser route-cost grids and metadata for all sites
- `web/index.html` shows aligned layers, allows manual checkpoint editing, and
  recalculates the route and safety summary
- README explains the real-data run in five steps or fewer
- At least three data views are layered and assumptions/placeholders are explicit
- Moon mode uses projection-meter map coordinates, labeled NASA products, and
  no fabricated lunar dose or terrain for regions without elevation data

## 9. Risks and Fallbacks

| Risk | Fallback |
|---|---|
| Mission coordinates are not supplied | Keep habitat and target coordinates visibly labeled as placeholders |
| Source product provenance is incomplete | State the missing product IDs and acquisition dates |
| A site has no valid route | Report the slope fraction and move placeholder points; do not relax thresholds |
| A dataset is unavailable | Keep the missing layer out of the default real-data path |

## 10. Pitch Outline

1. The problem: astronauts need a hyperlocal map and safe route summary.
2. The solution: aligned supplied imagery and terrain plus a route planner.
3. The data used, its provenance limits, and the explicit assumptions.
4. Live demo: switch sites, inspect layers, and jump between checkpoints.
5. Future work: replace coordinates and add validated science or environmental sources.
