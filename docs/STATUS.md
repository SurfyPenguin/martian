# Status (update after every task)

## Scope (MVP, solo, ~1 day)
- Area: ~5x5 km near Mount Sharp boxwork region, Gale Crater
- 4 layers: imagery, slope hazard map, CRISM/geologic map, radiation + weather panel
- 1 route between 2-3 science targets via A*
- 2-3 Mastcam photos for destination preview

## Definition of done
- `python scripts/slope.py && python scripts/route.py` produces data/processed/route.geojson
- Opening web/index.html shows layer toggles, route, and safety sidebar
- README explains how to run it in under 5 steps

## Done
- Added configurable placeholder AOI bounds and labeled EVA planning assumptions.
- Added a synthetic placeholder DEM generator and documented setup steps.

## In progress
Nothing.

## Next
1. scripts/slope.py
2. scripts/route.py
3. web/ Leaflet app
4. Safety sidebar, photos