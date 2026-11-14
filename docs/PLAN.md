# MarsWalk Planner: Project Plan

NASA Space Apps Challenge 2026, "Interplanetary Survival Guide: Martian Map".
Solo build. Full challenge text is in `docs/CHALLENGE.md`. Progress is tracked in
`docs/STATUS.md`.

## 1. Problem Statement

Astronauts planning a Marswalk need a hyperlocal view that combines terrain,
imagery, targets, route safety, and explicit mission assumptions. The current
tool focuses on two supplied, clipped sites and keeps the processing path
reproducible without reading external downloads.

**Goal:** Build a layered, interactive EVA planning map that combines supplied
NASA-provided DEM and CTX inputs with derived hazard and route information.

## 2. Solution: "MarsWalk Planner"

A tablet-style web app used to inspect a site, compare terrain layers, and plan
a route between placeholder science targets.

**Locations:** Two supplied sites in Gale Crater:
**Gale crater floor** and **Southern box**. The inputs are treated as
NASA-provided clipped files, but product IDs and acquisition dates were not
included in this repository.

**Science objective:** Demonstrate a low-risk EVA through three placeholder
science targets in each roughly 5 x 5 km site. Mission coordinates must replace
the placeholders before operational use.

**Scope (current MVP):**
- Two selectable sites
- CTX imagery, elevation, slope, and slope/roughness hazard layers
- One route between three placeholder science targets and back to habitat
- Assumption-based dose and EVA safety summary

## 3. Data Layers

| Layer | Type | Source | MVP? |
|---|---|---|---|
| CTX imagery | Optical | Supplied CTX raster | Yes |
| Elevation | Topographic | Supplied DEM raster | Yes |
| Slope / roughness hazard | Derived topographic | Computed from the supplied DEM | Yes |
| Route / targets | Navigation | A* output and placeholder coordinates | Yes |
| Dose estimate | Safety planning | Labeled `scripts/config.py` assumption | Yes |

The supplied files are the only real-data inputs in the current pipeline. Their
product IDs and acquisition dates are not available in this repository.

## 4. Key Features

1. **Layer toggles** for all current datasets on one map.
2. **Hazard map** flagging slope and rough terrain.
3. **Route planner:** A* pathfinding over slope and roughness cost between targets.
4. **Safety sidebar:** assumption-based dose estimate, EVA time budget, and
   distance back to habitat.
5. **Checkpoint controls:** clickable habitat and target stops with per-leg details.

## 5. Architecture

```text
data/raw/        external downloads (gitignored; never read by this pipeline)
scripts/
  config.py      site paths, coordinates, and labeled assumptions
  inspect_data.py  input schema inspection
  slope.py       DEM -> meter-scaled slope/roughness -> hazard and PNG layers
  route.py       A* over the cost map -> data/processed/<site>/
data/processed/  supplied inputs and per-site rasters, PNGs, route, stats, grid
web/
  index.html, app.js, style.css   Leaflet app
```

**Pipeline:** inspect supplied inputs -> compute meter-scaled slope and 5x5
roughness -> build traversability score -> run A* per site -> export aligned
PNG, GeoJSON, stats, and grid metadata -> Leaflet loads the selected site.

## 6. Assumptions

All adjustable assumptions live in `scripts/config.py` and are labeled in the
UI:

- Maximum walkable slope
- Maximum 5x5 elevation standard deviation
- Walking speed
- EVA duration
- Dose rate used only for a planning estimate

These are not verified mission measurements or predictions.

## 7. Execution Plan

| Step | Task |
|---|---|
| 1 | Validate the supplied site rasters and coordinate placeholders |
| 2 | Process slope, roughness, hazard, and aligned browser overlays |
| 3 | Run A* routes for both sites and inspect safety margins |
| 4 | Verify the Leaflet layers, site selector, safety sidebar, and checkpoints |
| 5 | Run the full pipeline and browser smoke checks |
| 6 | Prepare a demo and document remaining placeholders |

## 8. Definition of Done

- `python scripts/inspect_data.py` documents the supplied inputs
- `python scripts/slope.py --site site1` and `python scripts/route.py --site site1`
  produce that site's outputs; repeat for site2
- `web/index.html` shows aligned layers, route, checkpoints, and safety summary
- README explains the real-data run in five steps or fewer
- At least three data views are layered and assumptions/placeholders are explicit

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
