# Moon fix log

One entry per target, newest work described factually. Branch: `feat/moon`.

## Target 0 - diagnose only (2026-11-15)

- No code changes.
- Wrote `docs/MOON_DIAGNOSIS.md` with:
  - (a) metadata-only audit of all ten rasters in `data/raw/moon/`: sizes,
    pixel sizes, CRS names, `AREA_OR_POINT` (all `Area`), and bounds in
    projection meters read from the files; every CRS uses the 1,737,400 m
    spherical Moon radius.
  - (b) GeoJSON audit: no `crs` member, degree coordinates, longitude range
    -171.47..141.84 (-180..180 convention), 13 single-ring 5-vertex polygons
    with the full id/label table and projected footprint extents.
  - (c) contents of `backdrop.json`, `body.json`, `regions.json`, per-site
    `cost.json`/`grid.json`: bounds, transforms, units labeling, and a found
    10 m mismatch between documented (MOON_DATA_NOTES) and exported planning
    boxes for site_07 and sl3.
  - (d) the two-outline cause: `addRegionBoundaries()` (region footprint
    polygon from `regions.json`, permanent centered label) plus
    `addSiteBoundaries()` (5 x 5 km planning box from `body.json`, permanent
    corner label) - two rectangles and two name labels per named site.
  - (e) all four sites' data exist under `data/processed/moon/` and are
    preloaded with hidden overlays (`buildSiteLayers` +
    `setLayerVisible(false)`); only the active site's overlays are visible by
    design (`activateSite`).
  - (f) site_04 is unmatched because `config.py` sets `region_id: None` after
    the audit found the raster center inside no region polygon (nearest edge
    Connecting Ridge at 2.0 km; "Shackleton Rim" absent from the GeoJSON).
- Verified the pipeline projection round trip is exact (0.000000 mm) with the
  correct `(lat, lon)` argument order; my initial 1,539 km error was my own
  argument-order mistake in the test, not a pipeline bug.
