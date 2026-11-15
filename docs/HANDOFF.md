# Agent handoff: Martian Map

Updated 2026-11-15. Recheck the live repository before acting; this file is a
context summary, not a substitute for the code or project status.

## Read first

1. `docs/CHALLENGE.md` for the challenge brief.
2. `docs/PLAN.md` for the project scope.
3. `docs/STATUS.md` for completed and remaining work.
4. `README.md` for setup, use, data provenance, and limitations.
5. `docs/DATA_SCHEMA.md` for raster inputs and browser cost-grid formats.

Review notes in `docs/reviews/` describe older branches. Check their findings
against the current code before treating them as open issues.

## Project summary

Martian Map is a NASA Space Apps Challenge 2026 prototype for planning
candidate EVAs in Mars mode and a Moon south-pole demonstration mode. Mars
mode covers four sites in Gale Crater: **Gale crater floor**, **Southern box**,
**Rough terrain box**, and **Dune-edge box**. Moon mode uses four supplied
raster windows: **Connecting Ridge**, an unmatched `site_04` raster, **Peak
Near Shakleton**, and **Connecting Ridge Extension**. The project title is
"Martian Map." Routing is limited to the selected body's four high-resolution
sites; surrounding backdrops are context only.

The browser app visualizes supplied NASA CTX imagery and digital elevation
models (DEMs). Slope, roughness, hazard, and route layers are derived or
computed from those inputs. Mars uses one shared equirectangular map
projection; Moon uses south-polar stereographic meters. Site layers stay
loaded in the selected body's map projection.

Users can restore the automatic plan or add, move, remove, undo, and clear
checkpoints. The browser offers A*, Dijkstra, and Weighted A*, and selectable
Fastest, Safer, and Alternate routes. Manual checkpoint edits last only for
the current page session.

This is a demo planner, not a certified navigation or astronaut-safety tool.
Habitat and science-target coordinates are placeholders. The app has no
integrated lunar imagery, illumination, temperature, or radiation, and does
not provide mineral identifications.

## Current repository state

The Moon work is on branch `feat/moon`. The source audit and all four site
processing commits are present locally; site_04 remains explicitly unmatched
to the named-region GeoJSON. Check `git status --short --branch`,
`git log --oneline -8`, and `git worktree list --porcelain` before switching
branches or merging. Preserve uncommitted and untracked user files. Do not
assume remote branches or PR state are current, and do not push directly to
`main`.

## Data and processing

The site inputs are identified in the repository as NASA-provided, but their
product IDs and acquisition dates were not supplied. Do not invent provenance.
The clipped site inputs are in `data/processed/`; the schema and bounds are
documented in `docs/DATA_SCHEMA.md`.

Site3 and site4 use the requested fixed centers and windowed DEM/CTX clips.
Their measured site properties, per-site previews, route checks, edge cases,
and memory measurements are recorded in `docs/SITE_STRESS_TESTS.md`. Do not
run a scan over the large source DEM; the source inputs must only be read
windowed or decimated.

Moon source metadata, named-region features, selected planning bounds, and
LOLA support fractions are in `docs/MOON_DATA_NOTES.md`. Moon processing and
test measurements are in `docs/MOON_TESTS.md`. `scripts/make_moon_site.py`
is the lunar processor; it reads small output windows from the supplied
south-polar rasters and never reads a complete large source raster. The
10 m route grid uses the supplied slope raster and elevation-derived
roughness, with one slope/roughness/NoData hazard mask shared by the overlay
and route costs. The 1,000 m/pixel roughness backdrop is context only and uses
a 2nd-to-98th percentile display clip.

Moon coordinates use south-polar stereographic meters with a 1,737,400 m
radius. The 5 m LOLA count layer marks recorded returns; most 5 m surface
pixels are interpolated. The `site_04` raster midpoint is used because it does
not match a named region in the GeoJSON. Do not relabel it as Shackleton Rim.
Moon dose is not computed. Illumination, temperature, radiation, and imagery
are not integrated.

The local, git-ignored `data/raw/` directory contains large source files,
including `gale_ctx_blockadj_dd.tif` and `gale_dem_smg_1m.tif`. They are not
part of a clean clone. At the last local check, these source rasters were
about 1.8 GB and 5.8 GB respectively. `scripts/make_backdrop.py` reads them
with decimated reads; fixed site inputs may be cut only with explicit
windowed `gdal_translate -projwin -tr -r average` commands. Never scan or load a
full source raster into memory. The small generated backdrop assets are under
`web/data/`.

`scripts/slope.py` derives slope and 5 x 5 cell roughness from the clipped DEM.
One shared hazard mask marks slope above its configured limit, roughness above
its configured limit, and NoData. The overlay and Python/browser routers use
that mask. Hazard and safety-margin cells are impassable; diagonal movement
cannot cut blocked corners. The adjustable safety margin defaults to two
cells. A softer clearance cost affects route preference outside that margin.

The authoritative assumptions and site coordinates are in
`scripts/config.py`. Current labeled assumptions are:

- Maximum walkable slope: 15 degrees.
- Maximum 5 x 5 elevation standard deviation: 15 m.
- Safety margin: 2 cells by default, adjustable in the UI.
- Average walking speed: 3 km/h.
- EVA duration limit: 4 hours for the round trip.
- Dose estimate rate: 0.02 mSv per hour.

These are planning assumptions, not validated mission limits or measurements.
Do not relax thresholds to make a route succeed. Preserve the placeholder
labels until verified mission coordinates are provided.

Moon has separate labeled assumptions in `scripts/config.py`: 3 km/h walking
speed, four-hour EVA duration, 15-degree slope limit, 15 m roughness limit,
and two-cell safety margin. Moon has a `null` dose rate; never reuse the Mars
dose rate. These thresholds have not been relaxed for the high-hazard site_04.

The latest recorded automatic route outputs are 9.81 km / 3.27 h for site1,
18.619 km / 6.206 h for site2, 20.545 km / 6.848 h for site3, and 10.018 km /
3.339 h for site4. Sites2 and 3 are over the current four-hour assumption; do
not change assumptions to make them show as within the limit.
Re-run the route checks if inputs or settings change.

## Run and verify

The browser app is plain HTML, JavaScript, and Leaflet. There is no web build
step. From the repository root, serve it with:

```bash
python3 -m http.server 8000
```

Open `http://localhost:8000/web/`. See `README.md` for the Python environment,
GDAL, and data-regeneration instructions.

For each site, the processing commands are:

```bash
python scripts/slope.py --site site1
python scripts/route.py --site site1
python scripts/slope.py --site site2
python scripts/route.py --site site2
python scripts/slope.py --site site3
python scripts/route.py --site site3
python scripts/slope.py --site site4
python scripts/route.py --site site4
```

Run the hazard and algorithm checks with:

```bash
python scripts/check_hazards.py
node scripts/check_hazards.js
node scripts/check_algorithms.js
python scripts/check_moon.py --site site_01
node scripts/check_moon.js site_01
```

The latest recorded verification covered auto routes and 20 random
checkpoint sets per site, checked cells along route segments, and confirmed
that A* and Dijkstra costs agreed within 0.1% for 20 pairs per site. A browser
check also verified that a disconnected site4 checkpoint produces `NO SAFE
PATH` and rendered red dashed legs without console errors. The fixed site
windows, metrics, placeholder edge cases, and processing memory are recorded
in `docs/SITE_STRESS_TESTS.md`; image previews are in `docs/site_previews/`.
Moon site metrics and Python/JavaScript checks are in `docs/MOON_TESTS.md`.
The Moon verifiers check auto and random routes, target-line hazards, endpoint
snapping, disconnected-pocket no-path behavior, over-limit routes, coordinate
round trips, and A*/Dijkstra parity. Browser switching has been checked across
all Moon sites and back to each Mars site; site4 can correctly report `NO SAFE
PATH` for a manual checkpoint. Repeat relevant checks after changing route or
map code. For UI changes, run the page in a browser and check all sites and a
mobile viewport.

## Rules for future work

- Never fabricate NASA data, measurements, product IDs, or source dates.
- Keep every assumption in `scripts/config.py` and label it in the UI.
- Avoid unsupported geology and mineral claims. Keep real inputs, derived
  layers, placeholders, and assumptions clearly distinguished.
- Keep `data/raw/`, `*_full_res.tif`, and `*.aux.xml` out of commits. Never
  commit a file larger than 5 MB.
- Use a task branch and small Conventional Commits. Update `docs/STATUS.md`
  at the end of each task. Do not push directly to `main`.
- Run relevant tests and the browser page before claiming behavior works.
- Keep the app demoable without a JavaScript build step.

## Remaining work

1. Replace habitat and target placeholders only when verified mission
   coordinates are available.
2. Record source product IDs and acquisition dates if they can be verified.
3. Integrate environmental data only from validated sources; lunar dose is not
   computed and Mars radiation/weather estimates remain assumptions.
4. Treat older review notes as historical unless their findings are reproduced
   against the current code.
