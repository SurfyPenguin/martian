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
- Slope and binary hazard rasters generated from the placeholder DEM with
  nodata-safe edge handling
- A* EVA route through three placeholder science targets and back to habitat
- Leaflet demo with slope/hazard, route, target layers, opacity controls, and
  safety stats
- Steep placeholder ridge with visible red hazard cells and route detour
- Web map aligned on one row/column grid with padded fit and distinct return leg
- Added grid scale bar, north arrow, habitat-relative coordinate readout, and
  per-target leg tooltips
- Improved slope map with a cool-to-warm severity ramp and labeled degree key
- Route cost now penalizes steepness quadratically, favoring a gentler detour
- Refined tablet UI hierarchy, safety status, layer controls, and mobile layout
- Setup steps documented in README

## In progress
(nothing)

## Blocked on me
- Real DEM clip and imagery for the AOI (not downloaded yet)

## Next
1. Replace placeholder terrain and targets with documented NASA data
2. Add real surface imagery and destination photos
3. Add weather/radiation data sources and validation