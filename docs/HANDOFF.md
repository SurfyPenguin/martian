# Agent handoff: MarsWalk Planner

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

MarsWalk Planner is a NASA Space Apps Challenge 2026 prototype for planning
candidate EVAs at two supplied sites in Gale Crater: **Gale crater floor** and
**Southern box**. The README currently calls the project "Martian Map."
Routing is limited to the two roughly 5 x 5 km site areas; the surrounding
map is lower-resolution context only.

The browser app visualizes supplied NASA CTX imagery and digital elevation
models (DEMs). Slope, roughness, hazard, and route layers are derived or
computed from those inputs. Both site overlays stay loaded in one Mars map
projection. The site selector and site outlines fly between the two areas.

Users can restore the automatic plan or add, move, remove, undo, and clear
checkpoints. The browser offers A*, Dijkstra, and Weighted A*, and selectable
Fastest, Safer, and Alternate routes. Manual checkpoint edits last only for
the current page session.

This is a demo planner, not a certified navigation or astronaut-safety tool.
Habitat and science-target coordinates are placeholders. The app has no live
radiation or weather data and does not provide mineral identifications.

## Current repository state

At the start of this handoff update, local `main` was at `c180c43`, 15 commits
ahead of the locally recorded `origin/main` at `75a12ae`. The feature history
had been fast-forwarded into local `main`; this was not pushed. The remote is
configured over SSH, but SSH authentication failed in this environment, and
the GitHub CLI is not installed. Do not assume remote branches or PR state are
current, and do not push directly to `main`.

The handoff update is being made on `feat/handoff-context`, created from local
`main`. Check `git status --short --branch`, `git log --oneline -8`, and
`git worktree list --porcelain` before switching branches or merging. Preserve
uncommitted and untracked user files.

## Data and processing

The site inputs are identified in the repository as NASA-provided, but their
product IDs and acquisition dates were not supplied. Do not invent provenance.
The clipped site inputs are in `data/processed/`; the schema and bounds are
documented in `docs/DATA_SCHEMA.md`.

The local, git-ignored `data/raw/` directory contains large source files,
including `gale_ctx_blockadj_dd.tif` and `gale_dem_smg_1m.tif`. They are not
part of a clean clone. At the last local check, these source rasters were
about 1.8 GB and 5.8 GB respectively. Only `scripts/make_backdrop.py` may read
`data/raw/`. It uses decimated reads and GDAL command-line tools; never load a
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

The latest recorded automatic route outputs are 9.810 km / 3.270 h for site1
and 18.619 km / 6.206 h for site2. Site2 is over the current four-hour
assumption; do not change assumptions to make it show as within the limit.
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
```

Run the hazard and algorithm checks with:

```bash
python scripts/check_hazards.py
node scripts/check_hazards.js
node scripts/check_algorithms.js
```

The latest recorded verification covered auto routes and 20 random
checkpoint sets per site, checked cells along route segments, and confirmed
that A* and Dijkstra costs agreed within 0.1% for 20 pairs per site. Repeat
relevant checks after changing route or map code. For UI changes, run the page
in a browser and check both sites and a mobile viewport.

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
3. Integrate radiation or weather data only from a validated source; until then
   keep the dose estimate clearly labeled as an assumption.
4. Treat older review notes as historical unless their findings are reproduced
   against the current code.
