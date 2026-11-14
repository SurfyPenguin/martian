# MarsWalk Planner

This project is an interactive Mars EVA planning map for a small area near
Mount Sharp. The current DEM is explicitly synthetic placeholder data; replace
it with a documented NASA DEM before using the planner for science or mission
decisions.

The current setup only generates the placeholder DEM. The slope/route pipeline
and Leaflet planner described in the project plan are not implemented yet.

## Run the setup

1. Create and activate a Python 3.11+ virtual environment.
2. Install dependencies: `python -m pip install -r requirements.txt`
3. Generate the local placeholder DEM: `python scripts/make_placeholder_data.py`
4. Inspect the result at `data/processed/dem.tif`.

Adjust the AOI placeholders and planning assumptions in `scripts/config.py`.
Every planning value there is an assumption and must be replaced or validated
before a real-data demo.