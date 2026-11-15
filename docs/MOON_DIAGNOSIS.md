# Moon mode diagnosis (Target 0)

Diagnosis only; no code changes. All numbers below were read from the files
(metadata-only opens, no full raster reads) on 2026-11-15. Projection math used
`scripts/make_moon_site.py`'s own spherical south-polar stereographic functions
(`lon_lat_to_xy` / `xy_to_lon_lat`, R = 1,737,400 m). Those take `(latitude,
longitude)` and return `(latitude, longitude)` order; my first round-trip test
failed with a 1,539 km error because I passed the arguments in the wrong order.
With the correct order the round trip is exact: (-11000, -12000) m ->
lat -89.463162834, lon -137.489552922 -> (-11000.000000, -12000.000000) m,
error 0.000000 mm.

## a) Raster files in `data/raw/moon/`

All ten rasters are `AREA_OR_POINT=Area` (checked with both `gdalinfo` and
rasterio tags). With `Area`, the GeoTIFF geotransform already defines pixel
edges; GDAL's standard convention places samples at pixel centers halfway
inside those edges. No half-pixel correction is needed for these files as long
as geometry is computed from the geotransform edges. If any future file reports
`Point`, its geotransform refers to sample centers and edge bounds need a
half-pixel outward shift. Every CRS declares a spherical Moon radius of
1,737,400 m; no Earth ellipsoid appears anywhere.

| File | Disk size | Dims; pixel (m) | CRS name | AREA_OR_POINT | Bounds (projection m, from file) |
|---|---:|---|---|---|---|
| LDRM_80S_1000MPP_ADJ_ROUGH_100M.tiff | 1.5 MB | 608 x 608; 1000.0 / -1000.0 | Moon (2015) - Sphere / Ocentric / South Polar | Area | -304000 .. 304000 x, -304000 .. 304000 y |
| LRO_LOLA_Count_SPole875_5mp_v04.tif | 47.3 MB | 30336 x 30336; 5.0 / -5.0 | Moon2000_spole (GCS_Moon, Moon_2000_IAU_IAG) | Area | -75840 .. 75840 x, -75840 .. 75840 y |
| site_01_final_adj_5mpp_surf.tif | 41.0 MB | 3200 x 3200; 5.0 / -5.0 | unnamed (unnamed ellipse, R=1737400) | Area | -19000 .. -3000 x, -20000 .. -4000 y |
| site_01_final_adj_5mpp_slp.tif | 41.0 MB | 3200 x 3200; 5.0 / -5.0 | unnamed (same) | Area | -19000 .. -3000 x, -20000 .. -4000 y |
| site_04_final_adj_5mpp_surf.tif | 41.0 MB | 3200 x 3200; 5.0 / -5.0 | unnamed (same) | Area | -9000 .. 7000 x, -15000 .. 1000 y |
| site_04_final_adj_5mpp_slp.tif | 41.0 MB | 3200 x 3200; 5.0 / -5.0 | unnamed (same) | Area | -9000 .. 7000 x, -15000 .. 1000 y |
| site_07_final_adj_5mpp_surf.tif | 41.0 MB | 3200 x 3200; 5.0 / -5.0 | unnamed (same) | Area | 22000 .. 38000 x, -28000 .. -12000 y |
| site_07_final_adj_5mpp_slp.tif | 41.0 MB | 3200 x 3200; 5.0 / -5.0 | unnamed (same) | Area | 22000 .. 38000 x, -28000 .. -12000 y |
| sl3_final_adj_5mpp_surf.tif | 64.0 MB | 4000 x 4000; 5.0 / -5.0 | unknown (unknown, R=1737400, "Reference meridian") | Area | -38700 .. -18700 x, -16100 .. 3900 y |
| sl3_final_adj_5mpp_slp.tif | 64.0 MB | 4000 x 4000; 5.0 / -5.0 | unknown (same) | Area | -38700 .. -18700 x, -16100 .. 3900 y |

NoData: NaN for the Float32 roughness/surf/slp files; the count raster tags no
NoData and is Int16. The 5 m site rasters are all exactly 3,200 x 3,200 (16 km)
except sl3 at 4,000 x 4,000 (20 km). Pixel sizes are positive-x / negative-y,
row order north-up (standard GeoTIFF); nothing in the metadata suggests a y
flip.

## b) `A3_Named_regions_SP.geojson`

- CRS: **none** (no `crs` member; RFC 7946 default applies).
- Coordinate numbers are **degrees** (lon -171.46923439 .. 141.84277341, lat
  -89.83511068 .. -83.50154912).
- Longitude convention: **-180 .. 180** (values span -171.47 to 141.84; no
  value exceeds 180).
- 13 features, every one a `Polygon` with **1 exterior ring and 5 vertices**
  (4 corners + closing vertex). Property keys are only `label` and `selected`
  (all `selected: false`); the feature `id` is at feature level, not in
  properties.

| id | label | geom | polygons | rings | vertices |
|---:|---|---|---:|---:|---:|
| 0 | Amundsen Rim | Polygon | 1 | 1 | 5 |
| 1 | Nobile Rim 2 | Polygon | 1 | 1 | 5 |
| 2 | Haworth | Polygon | 1 | 1 | 5 |
| 3 | Faustini Rim A | Polygon | 1 | 1 | 5 |
| 4 | de Gerlache Rim 2 | Polygon | 1 | 1 | 5 |
| 5 | Connecting Ridge Extension | Polygon | 1 | 1 | 5 |
| 6 | Connecting Ridge | Polygon | 1 | 1 | 5 |
| 7 | Nobile Rim 1 | Polygon | 1 | 1 | 5 |
| 8 | Peak Near Shakleton | Polygon | 1 | 1 | 5 |
| 9 | de Gerlache Rim | Polygon | 1 | 1 | 5 |
| 10 | Leibnitz Beta Plateau | Polygon | 1 | 1 | 5 |
| 11 | Malapert Massif | Polygon | 1 | 1 | 5 |
| 12 | de Gerlache-Kocher Massif | Polygon | 1 | 1 | 5 |

Projected footprint extents (meters, computed with the spherical projection):

| id | label | x range (m) | y range (m) |
|---:|---|---|---|
| 0 | Amundsen Rim | 154000 .. 174000 | 51500 .. 71500 |
| 1 | Nobile Rim 2 | 147000 .. 167000 | 85000 .. 105000 |
| 2 | Haworth | -52900 .. -23100 | 75600 .. 105400 |
| 3 | Faustini Rim A | 54000 .. 74000 | -10000 .. 10000 |
| 4 | de Gerlache Rim 2 | -58500 .. -38500 | 13000 .. 33000 |
| 5 | Connecting Ridge Extension | -38700 .. -18700 | -16100 .. 3900 |
| 6 | Connecting Ridge | -19000 .. -3000 | -20000 .. -4000 |
| 7 | Nobile Rim 1 | 74000 .. 94000 | 100000 .. 120000 |
| 8 | Peak Near Shakleton | 22000 .. 38000 | -28000 .. -12000 |
| 9 | de Gerlache Rim | -45000 .. -29000 | 7000 .. 23000 |
| 10 | Leibnitz Beta Plateau | 65000 .. 81000 | 110000 .. 126000 |
| 11 | Malapert Massif | -11000 .. 10000 | 111000 .. 132000 |
| 12 | de Gerlache-Kocher Massif | -123400 .. -103400 | -66100 .. -46100 |

## c) Web app JSON (what each loaded layer says)

| File | Bounds / units content |
|---|---|
| `web/data/moon/backdrop.json` | bounds min_x -304000, min_y -304000, max_x 304000, max_y 304000 (matches the GeoTIFF bounds exactly); transform [2000, 0, -304000, 0, -2000, 304000] (the 304 x 304 PNG is 2,000 m/px, a factor-2 decimation of the 1,000 m source); "coordinate_system": "South polar stereographic, meters"; radius 1737400.0. Percentile clip [2, 98]. |
| `web/data/moon/body.json` | radius 1737400.0; per site: key, name, descriptor, region_id, 5 x 5 km `bounds` in meters (site_01 -13500..-8500 / -14500..-9500; site_04 -3500..1500 / -9500..-4500; site_07 27500..32500 / **-22510..-17510**; sl3 **-31210..-26210 / -8610..-3610**), plus grid/cost/asset paths. No explicit units field; coordinates are meters by the backdrop's declared system. |
| `web/data/moon/regions.json` | GeoJSON FeatureCollection, "Moon south polar stereographic meters"; per feature: name, source_id, site_key (sl3, site_01, site_07 set; null for the other ten), has_elevation_data, polygon in meters. **No per-feature lat/lon copy** and **no site_04 feature**. |
| `web/data/moon/<site>/cost.json` | rows/cols 500 x 500, cell_size_m 10 x 10, raster_transform (10 m), bounds in meters equal to body.json bounds, crs_wkt from the source raster, parameters (speeds km/h, margins in cells), dose_rate null. **No explicit units field.** |
| `data/processed/moon/<site>/grid.json` | geo_reference.bounds / transform in meters, `"cell_centers": true`, habitat/targets in row/col, layer_paths. Same bounds as cost.json. |

Mismatch found while diagnosing: `docs/MOON_DATA_NOTES.md` documents the
site_07 planning box as y -22500 .. -17500 and sl3 as x -31200 .. -26200,
y -8600 .. -3600, but the exported grids (grid.json, cost.json, body.json all
agree with each other) are offset by exactly **10 m**: site_07 y
-22510 .. -17510, sl3 x -31210 .. -26210, y -8610 .. -3610. The exports are
self-consistent; the notes text is what is off (or the box snap drifted). This
matters for any alignment test that compares the boxes against the documented
centers, and Target 1 must make the exported bounds the single source of truth.

## d) Why every named site is drawn with two outlines

Two independent drawing paths each add a rectangle and a permanent label:

1. **Region footprint polygon** - `addRegionBoundaries()`
   (`web/app.js:1195-1223`) draws `web/data/moon/regions.json` as an
   `L.geoJSON` layer (thin `#b8a8e8`, weight 1) and binds a **permanent,
   centered tooltip with the region name** to every feature (line 1206-1210).
   For the three DEM-backed regions the projected region polygons span the
   *full source raster footprint* (Connecting Ridge: x -19000 .. -3000,
   y -20000 .. -4000 = exactly the site_01 raster bounds; the rasters were
   clipped to the region polygons), so this outline is the 16-20 km region
   box.
2. **5 x 5 km planning box** - `addSiteBoundaries()`
   (`web/app.js:1113-1142`) draws an `L.rectangle` per site from
   `body.json` `sites[].bounds` (thin `#9c8bd0`) with a **second permanent
   tooltip holding the site name at the rectangle's top-left corner**
   (line 1129-1138). `activateSite()` (line 926-931) restyles the active
   site's same rectangle cyan (`#68e1fd`) - it does not add a third one.

So for Connecting Ridge, Connecting Ridge Extension, and Peak Near Shakleton
the map shows the region polygon (outer, 16-20 km) *and* the planning box
(inner, 5 km) plus **two permanent name labels each** - exactly the duplicated
labels in the screenshot. site_04 has only the planning box and one label,
because `regions.json` contains no site_04 feature. The nine regions without
DEMs are also drawn (they are simply outside the screenshot's current view;
Malapert Massif, for example, sits at y 111000 .. 132000, far north of the
view around y ~ -10000).

## e) Why "only one site loads"

It is not a data failure - all four sites' data exist and are preloaded:

- `data/processed/moon/` contains site_01, site_04, site_07, and sl3, each with
  the full output set: elevation.png/tif, grid.json, hazard.png/tif,
  hillshade.png, roughness.tif, slope.png/tif, stats.json, support.png/tif.
- `web/data/moon/<site>/` contains cost.bin, cost.json,
  clearance_cells.bin, clearance_meters.bin for all four.
- `loadPlanner()` runs `await Promise.all(siteManifest.map((site) =>
  loadSiteData(site)))` (`web/app.js:1104`), and `buildSiteLayers()`
  (line 713-791) **adds every site's hillshade/slope/hazard/support image
  overlays to the map immediately**, then hides them with
  `setLayerVisible(layer, false)` (line 784).
- `activateSite()` (line 907-931) makes visible **only the active site's**
  overlays: `const active = key === siteKey; ... setLayerVisible(layer, active
  && toggle.checked)` (line 916-921).

So at any moment exactly one site's imagery is visible - the other three are
loaded-but-hidden layers. The screenshot shows site_01 active with its overlays
visible; the other sites' rectangles are drawn but their imagery is hidden.
Switching sites (verified headlessly on 2026-11-15) activates the other site's
hidden overlays; nothing fails. If the product expectation is that each site's
overlays stay visible, that is a product decision for Target 4/5; the current
design is "load all, show one".

## f) Why site_04 is "unmatched"

- `scripts/config.py` sets `"region_id": None` and
  `"label": "site_04 raster (unmatched named region)"` for site_04 (the other
  three sites carry region_id 6, 8, and 5).
- `find_site_center()` (`scripts/make_moon_site.py:140-149`) returns the
  midpoint of the site_04 surface raster when `region_id` is None: center
  (-1000, -7000) m.
- Reason (measured for this diagnosis, point-in-polygon in projected meters):
  the site_04 raster center at (-1000, -7000) m is **inside no region
  polygon**. The nearest polygon edge is Connecting Ridge (id 6) at **2.0 km**
  (the raster overlaps that region's edge partially but its center lies
  outside), then Connecting Ridge Extension (id 5) at 17.7 km. The name
  "Shackleton Rim" does not occur anywhere in the GeoJSON (labels are listed in
  section b). For comparison, the three matched sites' raster centers equal
  their region centroids to 0.00 m (site_01 = region 6 centroid, site_07 =
  region 8, sl3 = region 5), confirming the rasters were cut centered on the
  named polygons.
- The earlier audit therefore refused to give site_04 a region identity and
  labeled it "unmatched". Under the current brief, Target 1+ will relabel it
  "Shackleton Rim (raster site_04; not in the A3 regions file)" - that label
  keeps the disclosure that it is not a GeoJSON-named region.

## Test

This file exists and answers (a) through (f) with real numbers read from the
files (raster metadata, GeoJSON contents, web JSON contents, and the cited
`web/app.js` / `scripts/make_moon_site.py` / `scripts/config.py` lines). No
code was changed for this target.
