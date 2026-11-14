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
- Route cost penalizes steepness while retaining an EVA-feasible detour
- Refined tablet UI hierarchy, safety status, layer controls, and mobile layout
- Added placeholder lat/lon metadata, an elevation-derived terrain layer,
  map reset/leg interactions, and a lat/lon/elevation/slope inspector
- Fixed layer stacking when toggling terrain and added high-contrast route
  casings with clearer outbound/return leg graphics
- Restyled the planner with a cobalt-inspired monochrome dark console,
  violet interaction accents, and compact utility controls
- Replaced the route badge with a restrained checkpoint timeline for the
  Habitat-to-target mission sequence
- Added a clearly labeled synthetic mineral-proxy layer with toggle, opacity,
  legend, and inspector zone values; no mineral identifications are claimed
- Increased synthetic terrain variance with rolling hills, crater-like
  depression, terrace, fine texture, and an elevation-balanced proxy map
- Slimmed outbound and return route strokes for a lighter map overlay
- Clarified the map inspector typography, moved it above zoom controls, and
  added selectable percentage zoom presets
- Reworked the north indicator as a compact grid-north compass
- Added a desktop sidebar resize handle with keyboard arrow support
- Switched the default pipeline to the supplied real DEM and CTX imagery for
  Gale crater floor and Southern box
- Added per-site input schema documentation, degree-to-meter Mars cell sizing,
  NoData masking, 5x5 roughness hazards, RGBA web exports, and site selection
- Generated real routes: 9.738 km / 3.246 h for Gale crater floor and
  5.955 km / 1.985 h for Southern box
- Setup steps documented in README
- Replaced the checkpoint strip with a collapsible mission top bar showing
  route totals, return margin, checkpoint coordinates, and per-leg distance/time
- Replaced zoom presets with an inline zoom percentage slider
- Improved terrain inspector hierarchy and kept it clear of map zoom controls

## In progress
(nothing)

## Blocked on me
- Habitat and target coordinates are placeholders pending mission-provided points
- Radiation and weather sources are not integrated yet

## Next
1. Replace placeholder habitat and target coordinates with mission points
2. Add destination photos and validate imagery provenance
3. Add weather/radiation data sources and validation