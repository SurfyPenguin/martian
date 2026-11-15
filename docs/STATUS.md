# Status (update after every task)

## Scope (MVP, solo, ~1 day)
- Four NASA-data sites in Gale Crater: Gale crater floor, Southern box,
  Rough terrain box, and Dune-edge box
- CTX imagery, elevation, slope/roughness hazard, route, and target layers
- Up to three hazard-safe route options between three placeholder science targets
  per site, with an adjustable algorithm and safety margin
- Assumption-based dose and EVA safety summary

## Definition of done
- `python scripts/slope.py --site <site>` and `python scripts/route.py --site <site>`
  produce per-site outputs
- Opening web/index.html shows layer toggles, route, and safety sidebar
- Shared hazard mask is the single source for the overlay and both routers;
  no route may cross a hazard or safety-margin cell
- Algorithm options report timing and explored cells; alternatives remain
  selectable and pass per-cell hazard verification
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
- Added a compact collapsed checkpoint control and clickable Habitat/target
  stops that fly the map to the selected coordinate
- Replaced zoom presets with an inline zoom percentage slider
- Improved terrain inspector hierarchy and kept it clear of map zoom controls
- Added Pillow to the documented dependencies and focused real-pipeline tests
- Made slope calculation explicitly NoData-safe without filling invalid elevations
- Reprojected CTX imagery onto each DEM transform before browser export
- Added provenance caveats, aligned the current project plan, and added a favicon
- Renamed slope variables to `slope_deg` and clarified the slope/roughness legend
- Refined the checkpoint control into a compact cobalt-style top bar with a
  clear expand/collapse state
- Replaced the floating terrain inspector card with a small bottom coordinate
  status bar showing latitude, longitude, grid position, and habitat range
- Moved zoom, zoom percentage, reset view, and grid-north navigation controls
  into a themed bottom-right control stack
- Grouped map navigation into one toggled `MAP TOOLS` dock and aligned its
  panel and checkpoint bar styling with the sidebar's layout and typography
- Made the scale bar choose a readable distance from the current zoom instead
  of stretching across the map or staying fixed at 1 km
- Added a decimated NASA CTX and DEM hillshade context generator; both WebP
  overview assets are under 3 MB, share the DEM footprint, and are about 18 m/px
- Added a shared Mars equirectangular projection for backdrops, site overlays,
  raster-cell centers, routes, targets, coordinate readout, and scale bar
- Kept all four sites' imagery, terrain, slope, hazard, route, and target layers
  loaded and positioned; added named site outlines and dropdown/outline fly-to
  switching with the safety summary and checkpoints updated after movement
- Added the low-resolution, no-route-data context label and clarified that the
  surrounding map is real NASA data; confirmed CTX texture continuity across
  both site boxes and browser switching without application console errors
- Exported per-site little-endian Float32 route-cost grids and metadata for
  browser routing without exposing full-resolution source rasters
- Added browser A* with live distance, time, dose, and return-margin estimates;
  passable-cell snapping; and explicit no-safe-path feedback
- Added visible checkpoint controls for map-click placement, dragging,
  delete/cancel, undo, clear, auto plan, and optional return to Habitat; manual
  checkpoint edits remain in memory per site for the current page session
- Added a mobile map/sidebar toggle so checkpoint placement remains accessible
  when the mission panel is hidden
- Verified Python/browser route parity for all eight stored route legs and
  exercised mobile checkpoint placement without console or network errors
- Made slope/roughness/NoData hazards one exported mask shared by the red overlay,
  Python routing, and browser costs; hazard cells are infinite-cost and diagonal
  moves cannot cut blocked corners
- Added a labeled, adjustable two-cell safety margin, six-cell soft clearance
  penalty, endpoint snapping, and cell-center route/overlay verification
- Verified all four sites' auto routes plus 20 random three-checkpoint sets per site
  in Python and JavaScript with Bresenham cell checks; synthetic diagonal-gap
  tests confirm corner cutting is blocked
- Added A* (octile), Dijkstra, and Weighted A* (default epsilon 1.5) choices,
  with optimality explanations, per-route time/exploration metrics, and
  A*/Dijkstra cost comparisons for 20 random pairs per site (all within 0.1%)
- Added selectable Fastest, Safer, and Alternate route cards with time, distance,
  dose estimate, minimum clearance, EVA-limit status, and map selection
- Captured route-card screenshots for both sites in docs/screenshots/
- Regenerated site routes: site1 9.810 km / 3.270 h (within limit); site2
  18.619 km / 6.206 h (over limit; assumptions were not relaxed)
- Unified map and form-control typography with the sidebar's monospace font;
  removed tight tracking from monospace titles and metadata
- Clarified checkpoint leg coordinates with labeled latitude/longitude rows,
  reduced detail-grid density, and auto-dismissed successful edit notices
- Fixed the map coordinate readout to read Leaflet `LatLng` coordinates, so
  backdrop coordinates and habitat distance stay numeric outside site bounds
- Verified refreshed Fastest, Safer, and Alternate cards are calculated by the
  browser planner; selecting each updates metrics and displays its distinct path
- Added 10% zoom slider steps and mapped 300% to the active site's checkpoint
  detail zoom, with the map's zoom-in controls capped at the same level
- Rewrote README setup and usage instructions; documented NASA dataset
  provenance limits, map layers, EVA assumptions, challenge links, and AI use
- Refreshed `docs/HANDOFF.md` with the current local merge state, app behavior,
  dataset limits, assumptions, verification commands, and remaining work
- Standardized project title references to "Martian Map" across documentation,
  repository agent guidance, and the backdrop generator's temporary directory prefix
- Added the fixed Rough terrain box and Dune-edge box sites from windowed NASA
  DEM/CTX clips, without scanning or loading the large source rasters; both
  retain the requested centers and have zero DEM NoData and full CTX coverage
- Recorded per-site elevation, imagery, hazard, passability, chokepoint, route,
  and A*/Dijkstra metrics with small CTX/hillshade previews in
  `docs/SITE_STRESS_TESTS.md`; site3's automatic route is 20.545 km / 6.848 h,
  while site4's is 10.018 km / 3.339 h
- Made site selection and site summaries data-driven from the generated
  four-site manifest, added the two new 5 x 5 km overlays and placeholder
  targets, and showed the slope/roughness limitation note for the new sites
- Verified all four sites with the Python and browser hazard checks, 80
  A*/Dijkstra comparisons, and the site3/site4 endpoint and EVA-limit checks;
  a headless browser test confirmed disconnected site4 legs show NO SAFE PATH
  and red dashed connectors without console errors
- Measured site3/4 processing and verification memory; the largest final
  verification RSS was 296,728 KB. Generated outputs remain under 5 MB, and
  no raw inputs or GDAL sidecars are included

## In progress
- Moon mode: source data audit is complete and `site_01` is processed with
  working body switching, lunar projection, layers, and route verification.
  The unmatched `site_04` raster is also processed and verified. `site_07`,
  with its source GeoJSON name preserved, is processed and verified. `sl3`,
  full lunar stress tests, and final documentation remain.

## Blocked on me
- Habitat and target coordinates are placeholders pending mission-provided points
- Radiation and weather sources are not integrated yet

## Next
1. Process and test the remaining lunar raster site without changing
   configured thresholds
2. Verify all Moon sites and repeat a browser route check on each Mars site
3. Replace placeholder habitat and target coordinates only when verified
   mission points are available
4. Record product IDs and acquisition dates if the source provenance is provided
5. Add validated radiation or weather sources before presenting them as layers