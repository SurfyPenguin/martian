# Moon fix log

One entry per target, newest work described factually. Branch: `feat/moon`.

## Target 1 - one source of truth for geometry (2026-11-15)

- Added `pyproj` to `requirements.txt` (installed pyproj 3.8.0) and created
  `scripts/moon_geo.py`: it builds a pyproj Transformer from the reference
  raster's own CRS (`site_01_final_adj_5mpp_surf.tif`, geodetic -> projected,
  `always_xy=True`), reads the spherical 1,737,400 m radius from that CRS, and
  refuses to run if the radius differs. No projection string is hardcoded.
- `moon_geo.py` now regenerates:
  - `web/data/moon/regions.json`: 14 features - the 13 GeoJSON regions plus a
    site_04 entry whose geometry is the supplied raster footprint and whose
    name is "Shackleton Rim (raster site_04; not in the A3 regions file)".
    Each feature carries `center` and polygon in projection meters
    (`geometry`) AND in lat/lon (`geometry_lonlat`, `center_lonlat`).
  - `web/data/moon/layers.json`: bounds in projection meters from the
    GeoTIFF edges for the backdrop (`LDRM_80S_1000MPP_ADJ_ROUGH_100M.tiff`)
    and each site's hillshade/slope/hazard/support (from their processed
    GeoTIFFs), with `AREA_OR_POINT` recorded and a half-pixel edge correction
    applied when `Point` (all current files are `Area`, so none needed).
- `web/app.js` Moon paths now read geometry only from these two files:
  backdrop overlay bounds + image path from `layers.json`
  (`addBackdrop`), site overlay/planning-box bounds from `layers.json`
  (`buildSiteLayers`), region outlines from `regions.json`. The processed
  grid stays the row/col -> meters mapping for routing only. Mars behavior
  and Mars geometry sources are unchanged.
- `make_moon_site.py` still contains its own inline regions.json writer; if
  the full pipeline is re-run, `scripts/moon_geo.py` must be re-run after it
  to restore the enriched regions.json/layers.json.
- Verification: pyproj reproduces the reference raster's own gdalinfo
  geographic corner to 0.008 m; all 14 region features round-trip
  lat/lon -> meters -> lat/lon with maximum error 0.000000018 m (< 0.01 m).
  Peak RSS 118,120 KB. Headless browser check in both bodies: no console
  errors.

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
