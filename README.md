# MarsWalk Planner

This project is an interactive Mars EVA planning map using the supplied real
DEM and CTX imagery for two clipped sites. Habitat and science-target
coordinates are clearly labeled placeholders in `scripts/config.py`. Dose,
radiation, walking speed, slope, roughness, and EVA duration are assumptions,
not mission measurements.

## Run the real-data demo

1. Create and activate a Python 3.11+ virtual environment.
2. Install dependencies: `python -m pip install -r requirements.txt`
3. Inspect inputs and generate the lower-resolution surrounding context:
   `python scripts/inspect_data.py && python scripts/make_backdrop.py`
4. Process both sites:
   `python scripts/slope.py --site site1 && python scripts/route.py --site site1`
   `python scripts/slope.py --site site2 && python scripts/route.py --site site2`
5. Serve the repository: `python -m http.server 8000`
   and open `http://localhost:8000/web/`.

The site selector loads **Gale crater floor** and **Southern box** outputs
from `data/processed/<site>/`; the surrounding map is real NASA data at lower
resolution for context only. Never put raw downloads in the repository or
read from `data/raw/` outside `scripts/make_backdrop.py`.

Use **Add checkpoint** on the map, then click inside the active site's outline
to add a route stop. Drag a checkpoint to move it; use Undo, Clear, or Auto
plan to edit the route. The optional return-to-Habitat toggle updates the route
and safety summary immediately. Manual stops last only for the current page
session.

Expand **Mission Checkpoints** to choose A*, Dijkstra, or Weighted A* and
compare the selectable Fastest, Safer, and Alternate routes. The sidebar's
safety-margin slider adjusts hazard clearance; mission points inside the margin
are snapped to free cells and reported.

Run the safety checks with `python scripts/check_hazards.py`,
`node scripts/check_hazards.js`, and `node scripts/check_algorithms.js`.

## Optional placeholder fallback

Synthetic generation is disabled by default and is never part of the web
pipeline. To explicitly create the legacy demo raster, run:

```bash
python scripts/make_placeholder_data.py --placeholder
```

Replace the placeholder habitat and target coordinates before using the route
for any mission planning.
