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
- Placeholder AOI bounds and labeled EVA assumptions in scripts/config.py
- Synthetic placeholder DEM generator (data/processed/dem.tif is NOT real NASA data)
- Slope and binary hazard rasters generated from the placeholder DEM
- Setup steps documented in README

## In progress
(nothing)

## Blocked on me
- Real DEM clip and imagery for the AOI (not downloaded yet)

## Next
1. scripts/route.py
2. web/ Leaflet app
3. Safety sidebar, photos