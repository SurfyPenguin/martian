# MarsWalk Planner

This project is an interactive Mars EVA planning map for a small area near
Mount Sharp. The current DEM is explicitly synthetic placeholder data; replace
it with a documented NASA DEM before using the planner for science or mission
decisions.

The demo runs entirely on clearly labeled synthetic placeholder terrain. It
includes slope/hazard processing, a low-risk A* route, and a Leaflet planning
map; replace the placeholder outputs with documented NASA data before mission
use.

## Run the demo

1. Create and activate a Python 3.11+ virtual environment.
2. Install dependencies: `python -m pip install -r requirements.txt`
3. Generate all processed data: `python scripts/make_placeholder_data.py && python scripts/slope.py && python scripts/route.py`
4. Serve the repository from the `web/` directory: `cd web && python -m http.server 8000 --directory ..`
5. Open `http://localhost:8000/web/`.

Adjust the AOI placeholders and planning assumptions in `scripts/config.py`.
Every planning value there is an assumption and must be replaced or validated
before a real-data demo.