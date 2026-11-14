# Real-data switch review

**Review basis.** The current checkout is `main`, so `git log main..HEAD` and `git diff main...HEAD` are empty by definition. The real-data work is present in `7b46ee1` and `3184931` (with later UI commits through `26bd147`); `git diff 7b46ee1^..HEAD` reports 8 files changed, 658 insertions and 530 deletions for the migration-related files. No merge was performed.

## Must fix

1. **Clean-clone setup omits Pillow.** `scripts/slope.py:12` imports `from PIL import Image`, but `requirements.txt:1-2` lists only `rasterio` and `numpy`. In a fresh virtual environment, `import PIL` returned `ModuleNotFoundError: No module named 'PIL'`; the README's dependency command therefore cannot guarantee that the documented pipeline runs. The attempted clean-venv `pip install -r requirements.txt` did not finish within four minutes while installing rasterio, so this is also a reproducibility risk. Add the actual image dependency and verify the README from a fresh environment.

2. **The CTX export is resized but not spatially aligned to the DEM.** `scripts/slope.py:99-107` calls `source.read(out_shape=shape)` without using the imagery transform/bounds or reprojecting/cropping it to the DEM grid. The browser then assigns the result the DEM grid bounds via `web/app.js:235-237`. Evidence from `docs/DATA_SCHEMA.md:7-10`: site1 DEM bounds are `(137.3837293189, -4.6294578194, 137.4685673189, -4.5449578194)` while its imagery bounds are `(137.3836794254, -4.6295525992, 137.4685385434, -4.5449465402)`; site2 also differs. The layers are visually close, but this violates the real-data requirement that overlays share the same bounds and can shift CTX relative to terrain/routes. Reproject/resample imagery onto the DEM transform/grid, then regenerate the PNGs.

3. **Slope is calculated through a fake filled surface before being masked.** `scripts/slope.py:52-60` replaces invalid cells with `0.0`, runs `np.gradient`, then masks cells whose cardinal neighbors are invalid. The output safety check passed—including an injected NoData test (`center_and_neighbors_nan=True`)—and both supplied DEMs currently contain zero NoData cells, but the implementation still computes gradients from fabricated zero elevations. This is not the requested “never compute slope across NoData” behavior and is unsafe if a gap is introduced inside a valid region. Use a neighborhood-valid calculation that never uses filled NoData values.

4. **Project documentation still presents removed or prohibited scope as current.** `docs/PLAN.md:21-25,38-46` claims a Mount Sharp/boxwork objective and CRISM/RAD/REMS-derived layers; `docs/STATUS.md:4-7` repeats Mount Sharp/boxwork and lists CRISM/geology and radiation/weather in scope, while `docs/STATUS.md:10` still documents commands without the now-required `--site`. The actual UI only has real DEM/CTX, derived slope/hazard, placeholder targets, and assumption-based dose. This conflicts with the requested labels and makes the submission misleading. Update the current plan/status to describe what is actually implemented; do not rewrite the challenge source text.

## Should fix

1. **Make degree units explicit in code names.** The requested convention is `slope_deg`, but `scripts/slope.py:45-60,125-140` uses generic `slope`, and `scripts/route.py:40-42,133-163` follows that naming. The numerical spot check was correct: site1 cell `(1,1)` hand-calculated to `0.95328554°` versus raster `0.95328563°`; site2 was `17.56398694°` versus `17.56398582°`. Rename variables/outputs or add an explicit unit boundary so degree/radian mistakes cannot be hidden.

2. **Clarify the hazard legend.** `web/index.html:57` labels the red layer “Too steep,” but `scripts/slope.py:129-134` marks both slope and roughness hazards and the adjacent copy at `web/index.html:66` says “slope or roughness.” Change the legend to state slope/roughness hazard.

3. **Keep the generated schema truthful about provenance.** `docs/DATA_SCHEMA.md:3-12` calls the inputs “real” and the processing tags at `scripts/slope.py:144-154` say “supplied NASA DEM,” but the repository does not record the source product IDs, acquisition dates, or download provenance. Add provenance before presenting the data as NASA-derived in a judged demo.

## Nice to have

1. Add automated tests for the hand-calculated slope, injected NoData neighborhood, diagonal distance, EVA failure, impassable endpoints, and route/hazard sampling. The manual checks below passed, but these safety invariants are not protected against regression.

2. Remove the unused `read_dem()` helper at `scripts/slope.py:35-42`, unused `dem_bounds` at `scripts/route.py:129-132`, and unused `KM_PER_DEG` at `scripts/config.py:9` to reduce ambiguity in the reviewed pipeline.

3. Add a favicon or suppress the missing request. Browser validation produced one non-application error: `Failed to load resource: the server responded with a status of 404 (File not found)` for `/favicon.ico`.

## Evidence and executed checks

### Pipeline output

The README commands were run for both sites in the repository and again from a `git archive HEAD` clean tree. All five commands returned status 0:

```text
site1: cell size x=9.966 m, y=9.998 m; slope>15° in 0.18% of valid cells; hazard cells=4437
site1: cell size x=9.966 m, y=9.998 m; slope>15° in 0.18% of valid slope cells
site1: route 9.738 km, 3.246 h
site2: cell size x=9.963 m, y=9.998 m; slope>15° in 34.69% of valid cells; hazard cells=89617
site2: cell size x=9.963 m, y=9.998 m; slope>15° in 34.69% of valid slope cells
site2: route 5.955 km, 1.985 h
CLEAN_STATUS slope1=0 route1=0 slope2=0 route2=0
```

Final stats are site1: `9.738 km`, `3.246 h`, `0.754 h` return margin, `0.1833` slope-over-limit fraction, cell `9.966 x 9.998 m`; site2: `5.955 km`, `1.985 h`, `2.015 h` margin, `0.346896` fraction, cell `9.963 x 9.998 m`.

### Data and route checks

- `scripts/slope.py:22-32` reads `source.res`, checks a geographic CRS, uses `MARS_RADIUS_M * pi / 180`, and applies `cos(latitude)` east-west. The printed cells are approximately 10 m as required.
- Both supplied DEMs had `dem_nodata=0`; derived slope NoData counts were 0. Roughness edge NoData counts were 3992 (site1) and 3996 (site2), consistent with requiring a complete 5x5 window. The injected NoData test returned `INJECTED_NODATA_CENTER_AND_NEIGHBORS_NAN True` and `...FAR_CELL_FINITE True`.
- Route sampling returned `route_hazard_unique=[0]` for both sites; maximum route slope was `14.178355°` / `14.925613°`, and maximum route roughness was `2.573003 m` / `4.481300 m`.
- The diagonal cost and distance use `math.hypot` with real x/y cell sizes at `scripts/route.py:71-74` and `115-122`; time is distance divided by `WALKING_SPEED_KMH` at `scripts/route.py:174-175`; margin is `EVA_HOURS - time_h` at `scripts/route.py:190-195`.
- With `route.EVA_HOURS=0.001`, the route failed as expected: `RuntimeError: site1 route requires 3.25 h, over the 0.00 h EVA assumption; move the placeholder habitat or targets.` A target moved to hazard pixel `(0, 0)` failed clearly: `RuntimeError: site1 has no valid route with the configured assumptions: Route endpoint is not walkable: (250, 251) -> (0, 0). Move the placeholder habitat or targets; do not relax thresholds.`
- `git log -p -- scripts/config.py` shows `MAX_WALKABLE_SLOPE_DEG = 15.0`, `MAX_ROUGHNESS_M = 15.0`, `WALKING_SPEED_KMH = 3.0`, and `EVA_HOURS = 4.0` added as labeled settings; no history showed a threshold being relaxed to make these routes succeed.
- `rg` found no code read of `data/raw/`. `scripts/make_placeholder_data.py:78-87` rejects execution unless `--placeholder` is supplied.

### Web checks

A local HTTP server loaded both sites in a clean headless browser. The browser-side result was:

```text
first:  site1 / Gale crater floor / 4 image overlays / route site1
second: site2 / Southern box / 4 image overlays / route site2 / 5.955 km / 2.015 h margin
```

No application exceptions or console errors occurred. The only browser error was the missing `/favicon.ico` 404 noted above. Site switching updated the site name, route, distance, margin, and image overlays; no stale site route was observed. `web/app.js:1-17,235-258` uses one grid conversion and shared `grid_bounds`; `web/app.js:242-257` clearly distinguishes dashed amber outbound from solid cyan return, and `web/app.js:78-94` computes a 1 km scale bar from the current site's x cell size.

PNG inspection found all four exports per site are RGBA 8-bit at the DEM shape (`502x500` site1, `502x501` site2). Scalar exports use `rgba_from_scalar()` min/max scaling at `scripts/slope.py:77-92`; NoData/invalid pixels are alpha 0. Hazard is intentionally a red categorical overlay with transparent non-hazard cells. No Site 1 elevation range is hardcoded.

### Repository hygiene

```text
RAW_TRACKED=0
FULL_RES_TRACKED=0
AUX_TRACKED=0
largest tracked files: site1_imagery_8bit.tif 988K, site2_imagery_8bit.tif 992K
```

No tracked file exceeded 5 MB. No `data/raw/`, `*_full_res.tif`, or `.aux.xml` files are tracked.

## Demo risk

**Not safe to demo and submit yet.** The normal checked-in environment produces both routes, but a fresh clone can fail before the first slope command because Pillow is not declared. The CTX layer can be visibly offset from the DEM by the input-bound differences, and the documentation can cause judges to believe CRISM/radiation/weather or the prohibited location language is part of the current product. The browser also emits a favicon 404, which is minor but visible in console checks. After the four Must fix items are resolved and the clean-clone pipeline is rerun, the core route output is otherwise demoable: both routes stay within the 4-hour assumption and sampled route cells are hazard-free.
