# Moon source-data inspection

This inspection used `ls -lh`, `gdalinfo -nomd` on every raster, and decimated
512 x 512 reads for raster value ranges. The LOLA return-count map was sampled
with maximum resampling because average-resampling to its integer type erases
sparse positive counts. Site support percentages below come from exact
1,000 x 1,000 pixel windows of the 5 m count raster. No full source raster was
read into memory. The largest measured inspection RSS was 160,456 KB.

## Raster inputs

All rasters report projected coordinate axes in meters and a polar
stereographic projection centered at 90 degrees south, central meridian 0,
scale factor 1, and zero false easting/northing. The files use different CRS
names or unknown datum labels, but each WKT declares a spherical lunar radius
of 1,737,400 m and the same projection parameters. The GeoJSON has no `crs`
member; its coordinates are treated as longitude, latitude per RFC 7946.

The band-unit metadata and rasterio unit fields are absent. Spatial units are
meters, but raster sample units are not explicitly declared in these files.
The surf, slope, roughness, and count value ranges below are therefore reported
as native sample values. The slope comparison in the site-processing report
will document whether the supplied slope values agree with the calculated
degree slope; that comparison does not add missing source metadata.

| Input | File size | Dimensions; pixel size | CRS name | Band dtype; NoData | Decimated min/max |
|---|---:|---|---|---|---:|
| `LDRM_80S_1000MPP_ADJ_ROUGH_100M.tiff` | 1.5 MB | 608 x 608; 1,000 m | Moon (2015) sphere / Ocentric / South Polar | Float32; NaN | 0.3023 / 1.6370 |
| `LRO_LOLA_Count_SPole875_5mp_v04.tif` | 46 MB | 30,336 x 30,336; 5 m | Moon2000_spole | Int16; none tagged | 0 / 5 (512 x 512 maximum-resampled overview) |
| `site_01_final_adj_5mpp_surf.tif` | 40 MB | 3,200 x 3,200; 5 m | Unnamed South Polar Stereographic | Float32; NaN | -518.440 / 1,958.402 |
| `site_01_final_adj_5mpp_slp.tif` | 40 MB | 3,200 x 3,200; 5 m | Unnamed South Polar Stereographic | Float32; NaN | 0.604 / 36.972 |
| `site_04_final_adj_5mpp_surf.tif` | 40 MB | 3,200 x 3,200; 5 m | Unnamed South Polar Stereographic | Float32; NaN | -2,846.415 / 1,803.443 |
| `site_04_final_adj_5mpp_slp.tif` | 40 MB | 3,200 x 3,200; 5 m | Unnamed South Polar Stereographic | Float32; NaN | 0.437 / 42.910 |
| `site_07_final_adj_5mpp_surf.tif` | 40 MB | 3,200 x 3,200; 5 m | Unnamed South Polar Stereographic | Float32; NaN | -415.613 / 1,648.388 |
| `site_07_final_adj_5mpp_slp.tif` | 40 MB | 3,200 x 3,200; 5 m | Unnamed South Polar Stereographic | Float32; NaN | 0.348 / 36.046 |
| `sl3_final_adj_5mpp_surf.tif` | 62 MB | 4,000 x 4,000; 5 m | Unknown South Polar Stereographic | Float32; NaN | -1,162.175 / 1,692.479 |
| `sl3_final_adj_5mpp_slp.tif` | 62 MB | 4,000 x 4,000; 5 m | Unknown South Polar Stereographic | Float32; NaN | 0.369 / 35.488 |

The `surf` and `slp` pairs have matching extents for each id. Their shared
projected bounds are: site_01 x -19,000 to -3,000 m, y -20,000 to -4,000 m;
site_04 x -9,000 to 7,000 m, y -15,000 to 1,000 m; site_07 x 22,000 to
38,000 m, y -28,000 to -12,000 m; and sl3 x -38,700 to -18,700 m, y -16,100
to 3,900 m.

The low-resolution roughness backdrop spans x/y -304,000 to 304,000 m. The
LOLA count raster spans x/y -75,840 to 75,840 m. All four selected planning
boxes fit inside both of those rasters and inside their corresponding
site-specific surface and slope rasters. Band values have no unit tags; the
requested Moon labels will state the product/resolution and the limits of
interpretation rather than inventing additional source units.

## Named-region GeoJSON

Feature coordinates below are the original polygon vertices, in
`longitude,latitude` order; the repeated closing vertex is omitted. A feature
has a matching site DEM only where the supplied raster footprint and region
identification agree. The site_04 raster is not assigned the user-suggested
name “Shackleton Rim”: that name does not occur in the GeoJSON, and its raster
center is outside every named polygon. A 100 m point sample finds only partial
overlap with Connecting Ridge, so site_04 remains a separately labeled,
unmatched DEM window rather than being presented as that region.

| GeoJSON id | Name exactly as supplied | Polygon vertices (lon, lat) | Matching DEM |
|---:|---|---|---|
| 0 | Amundsen Rim | (65.09523119,-84.40517285); (67.66128158,-83.80232774); (73.51245734,-84.02121673); (71.50926173,-84.64884385) | No |
| 1 | Nobile Rim 2 | (54.46232221,-84.04794193); (57.84067901,-83.50154912); (63.02472352,-83.82634302); (59.96215525,-84.40461580) | No |
| 2 | Haworth | (-26.65196166,-86.11239815); (-12.36178188,-86.44277414); (-16.99082329,-87.39353361); (-34.98184604,-86.95784228) | No |
| 3 | Faustini Rim A | (79.50852299,-88.18906723); (82.30394828,-87.53783384); (97.69605172,-87.53783384); (100.49147701,-88.18906723) | No |
| 4 | de Gerlache Rim 2 | (-60.57254360,-87.78528838); (-49.39870535,-88.32789270); (-71.34211153,-88.65998570); (-77.47119229,-88.02392883) | No |
| 5 | Connecting Ridge Extension | (-84.24543467,-88.71734521); (-78.21947622,-89.37005103); (-130.72721923,-89.18625468); (-112.58832020,-88.61778604) | Yes: sl3 |
| 6 | Connecting Ridge | (-101.88865804,-89.35969194); (-143.13010235,-89.83511068); (-171.46923439,-89.33307106); (-136.46880071,-89.09028361) | Yes: site_01 |
| 7 | Nobile Rim 1 | (31.66075110,-85.35325142); (38.07278187,-84.97628329); (43.22853026,-85.47632419); (36.50144112,-85.89921757) | No |
| 8 | Peak Near Shakleton | (118.61045967,-89.17359087); (107.52556837,-88.68589815); (126.38435182,-88.44348361); (141.84277341,-88.82573196) | Yes: site_07 |
| 9 | de Gerlache Rim | (-62.92791976,-88.33351026); (-51.58194466,-88.77941881); (-76.42956561,-89.01619925); (-81.15818544,-88.49823380) | No |
| 10 | Leibnitz Beta Plateau | (27.28798795,-85.32705340); (32.73522627,-85.06330364); (36.36658017,-85.49736561); (30.57922687,-85.78833524) | No |
| 11 | Malapert Massif | (-4.76364169,-85.63394425); (4.33231398,-85.63655542); (5.14788482,-86.32588928); (-5.65948184,-86.32278684) | No |
| 12 | de Gerlache-Kocher Massif | (-110.48477552,-85.65790523); (-114.02929120,-86.26785495); (-122.58935728,-85.95455847); (-118.17601311,-85.38597152) | No |

The GeoJSON spelling “Peak Near Shakleton” is retained for fidelity to the
source, although the request spells it “Shackleton.” No other region names
listed in the request are substituted for source labels.

## Planned routing boxes and LOLA support

For the three matching regions, the center is the polygon centroid calculated
after converting the GeoJSON longitude/latitude coordinates to the source
South Polar Stereographic meters. site_01, site_07, and sl3 centroids equal
their raster centers. Since site_04 has no matching GeoJSON feature, its
planning window uses the midpoint of the site_04 surface raster; this is an
explicit fallback, not a named-region coordinate.

Each box is 5,000 x 5,000 m, aligned to the 10 m output grid. Support is the
fraction of original 5 m LOLA count pixels with a value greater than zero;
zero means no laser return is recorded in that pixel.

| Site raster | Center x, y (m) | Box x min/max; y min/max (m) | Center source / region | LOLA pixels with returns |
|---|---|---|---|---:|
| site_01 | -11,000, -12,000 | -13,500 / -8,500; -14,500 / -9,500 | Connecting Ridge | 8.3265% |
| site_04 | -1,000, -7,000 | -3,500 / 1,500; -9,500 / -4,500 | Raster midpoint; no matching named region | 8.1837% |
| site_07 | 30,000, -20,000 | 27,500 / 32,500; -22,500 / -17,500 | Peak Near Shakleton | 6.5337% |
| sl3 | -28,700, -6,100 | -31,200 / -26,200; -8,600 / -3,600 | Connecting Ridge Extension | 2.9667% |

The site_04 mismatch is documented and not hidden or relabeled. Its center is
about 12 km from the centroid of the nearest GeoJSON region, and the request's
“Shackleton Rim” label is absent from the source file. The implementation will
show its data as an unmatched site raster and continue to draw the 13
source-named regions exactly as supplied.
