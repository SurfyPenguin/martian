# MarsWalk Planner: Project Plan

NASA Space Apps Challenge 2026, "Interplanetary Survival Guide: Martian Map".
Solo build. Full challenge text is in `docs/CHALLENGE.md`. Progress is tracked in `docs/STATUS.md`.

## 1. Problem Statement

Mars Trek and the USGS-NASA geologic maps give regional and global views of Mars. Astronauts on a
Marswalk need a hyperlocal view of a few kilometers that combines terrain, science targets,
radiation, weather, and safety limits. Today those datasets live in separate tools and formats, so
no single view tells a crew where they can safely walk, what science is worth doing, and when they
must turn back.

**Goal:** Build a layered, interactive EVA (spacewalk) planning map that merges multiple NASA Mars
datasets and generates a safe, science-driven walking route for human explorers.

## 2. Solution: "MarsWalk Planner"

A tablet-style web app. Used in the habitat to plan the EVA, and carried on the EVA to navigate.

**Location:** Mount Sharp region, Gale Crater, near the boxwork formations Curiosity studied.
Chosen because Curiosity has measured radiation (RAD), weather (REMS), and chemistry there, and
orbital imagery (HiRISE, CTX) and mineral data (CRISM) cover the area.

**Science objective:** Study boxwork ridges and the surrounding clay- and sulfate-bearing units.
Pick 2-3 targets inside a ~5 x 5 km area.

**Scope (solo MVP):**
- One ~5 x 5 km area
- 4 layers (see below)
- One route between 2-3 science targets
- 2-3 Mastcam photos for the destination preview

## 3. Data Layers

The challenge asks for at least three kinds of data. We use four map/panel layers and add more if time allows.

| Layer | Type | Source | MVP? |
|---|---|---|---|
| Imagery | Optical | HiRISE (~25-30 cm/px), CTX (~6 m/px) | Yes |
| Slope / hazard | Topographic | MOLA/HRSC blended DEM (~200 m/px, coarse) or HiRISE DTM if one covers the area | Yes |
| Minerals / geology | Spectral | CRISM browse products, USGS-NASA geologic map | Yes |
| Radiation + weather | Radiation, atmospheric | Curiosity RAD and REMS (PDS) | Yes (dashboard numbers) |
| Thermal | Thermal | THEMIS mosaics | Stretch |
| Chemistry | Chemical | ChemCam / APXS | Stretch |
| First-person view | Optical | Curiosity Mastcam images | Yes (2-3 photos) |

**Where to get the data:**
- JMARS (jmars.asu.edu) and Mars Trek (trek.nasa.gov/mars): check coverage and export subsets
- USGS Astropedia: DEMs and geologic maps
- HiRISE site (hirise.lpl.arizona.edu): imagery and DTMs
- PDS Geosciences Node: CRISM and RAD
- PDS Atmospheres Node (atmos.nmsu.edu): REMS
- mars.nasa.gov/msl: Curiosity raw images

## 4. Key Features

1. **Layer toggles** for all datasets on one map.
2. **Hazard map** flagging steep slopes and rough terrain (boulder layer only if data allows).
3. **Route planner:** A* pathfinding over a slope-based cost map between science targets.
4. **Safety sidebar:** estimated radiation dose for the route, EVA time budget, distance back to
   the habitat/rover, weather and dust outlook.
5. **Destination preview** with real surface photos.
6. **Pair mode (stretch):** two astronauts, a rover carrying gear, and a "turn back" warning.

## 5. Architecture

```
data/raw/        downloaded NASA data (gitignored)
scripts/
  config.py      all assumptions (max slope, walking speed, dose rate), clearly commented
  slope.py       DEM -> slope raster -> hazard / traversability raster
  route.py       A* over the cost map -> data/processed/route.geojson
data/processed/  small outputs: clipped rasters, route.geojson, stats.json
web/
  index.html, app.js, style.css   Leaflet app: layers, route overlay, safety sidebar
```

**Pipeline:** clip DEM to the area -> compute slope -> build traversability score -> A* route ->
export GeoJSON + stats JSON -> Leaflet app reads them.

## 6. Assumptions (must be adjustable in `config.py` and shown in the UI)

- Max walkable slope for a suited astronaut (e.g. 15-20 degrees; to be confirmed and labeled as an assumption)
- Walking speed on Mars in a suit
- EVA duration limit and required reserve for the return trip
- Radiation dose rate (estimated from Curiosity RAD measurements at Gale; an estimate, not a prediction)

Never present these as verified NASA figures. Label them as assumptions.

## 7. Execution Plan

| Step | Task | Time |
|---|---|---|
| 1 | Define mission: choose area and 2-3 science targets, confirm coverage in JMARS / Mars Trek | 1 h |
| 2 | Collect data: DEM clip, HiRISE/CTX imagery, CRISM or geologic map, RAD/REMS values, Mastcam photos | 3-4 h |
| 3 | Process: compute slope, build hazard raster and traversability score | 4 h |
| 4 | Route engine: A* with slope cost plus time and distance limits, export GeoJSON | 4 h |
| 5 | Interface: Leaflet map, layer panel, safety sidebar, photo preview | 6 h |
| 6 | Test: run a full sample EVA, fix bugs, capture screenshots | 3 h |
| 7 | Demo: short video and pitch deck | 2 h |

Until real data is downloaded, the coder uses clearly labeled placeholder data with configurable paths.

## 8. Definition of Done

- `python scripts/slope.py && python scripts/route.py` produces `data/processed/route.geojson`
- `web/index.html` shows layer toggles, the route, and the safety sidebar
- README explains how to run it in 5 steps or fewer
- At least 3 kinds of data are layered, and safety info is shown

## 9. Risks and Fallbacks

| Risk | Fallback |
|---|---|
| A dataset has no coverage or is too coarse at the chosen spot | Pick a nearby spot, or use the geologic map and CTX instead |
| CRISM raw formats are hard to process | Use pre-made browse/map-projected products |
| No fine-resolution DEM | Use the coarse DEM, and state the resolution limit openly |
| Time runs short | 4 layers and one hand-planned route still meets the challenge |
| Radiation data is rover-measured only | Present dose as an estimate with the method stated |

## 10. Pitch Outline

1. The problem: astronauts need a hyperlocal map, not a global one.
2. The solution: a layered map plus an automatic safe-route planner.
3. The data we used and why.
4. Live demo: a sample Marswalk with its route and safety stats.
5. Future work: HUD visor version, live space-weather updates, other landing sites.