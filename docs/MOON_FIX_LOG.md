# Moon fix log

One entry per target, newest work described factually. Branch: `feat/moon`.

## Target 2 - automated alignment tests (2026-11-15)

- Added `scripts/check_moon_alignment.py`: prints a PASS/FAIL table and exits
  nonzero on any FAIL. Python side uses `moon_geo.py` (pyproj transformer from
  the raster's CRS); browser side runs the web app's own `web/geo.js`
  functions (`gridToMap`, `latLonToMap`, `moonXYToLonLat`, `setGeoReference`)
  under Node.
- Coverage: (a) all 17 overlay layers' `layers.json` bounds vs their GeoTIFF
  bounds within one pixel plus PNG shape vs raster shape at the overlay's own
  resolution; (b) highest and lowest elevation pixel of each site's
  elevation GeoTIFF mapped through Python and through the browser's own
  `gridToMap`, agreeing within one 10 m cell (no y flip, no x shift);
  (c) all 14 region centers equal across geojson->Python, `regions.json`, and
  the browser; (d) JS inverse projection vs Python within 1 m (measured
  0.0000 m) on 5 test points; (e) backdrop overlay width/height equals
  cols/rows x 1,000 m exactly.
- Result: 45/45 PASS on the current branch. The alignment of the existing
  data exports and browser code was verified correct; no data or JS fixes
  were needed. The three first-run FAILs were bugs in the checker itself and
  were fixed in the checker (documented here so the history is honest): the
  Python y used the wrong affine coefficient (`transform[3]` instead of
  `transform[4]`), the JS inverse test fed lon/lat degrees where projected
  meters were required, and the backdrop PNG-shape check demanded 1:1
  resolution although that PNG is deliberately decimated to 2,000 m/px
  (608 -> 304, recorded in `backdrop.json`).
- Peak RSS 123,900 KB.

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
