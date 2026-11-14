# Review: feat/slope

## Must fix

- `scripts/slope.py:15-18,32-35` does not handle nodata neighborhoods. It computes `np.gradient` across the DEM before masking nodata cells, so valid cells next to nodata receive fake edge slopes. A direct test with a nodata top row (`-9999`) produced approximately `89.994` degrees in the nodata row and `89.989` degrees in the adjacent valid row, even though the valid terrain was flat. Mask or otherwise handle nodata before/after gradient calculation so no valid edge cell is contaminated.
- `scripts/slope.py:15-18,32-35,55-60` names the calculated raster `slope`, not `slope_deg`, despite the required degrees-specific naming. Rename the slope variables and related outputs in the implementation so degree units are unambiguous throughout.

## Should fix

- `scripts/slope.py:17-18` uses the DEM transform resolution directly, which is correct for a projected DEM but the committed placeholder DEM has no CRS and its cell sizes are degrees while its synthetic elevations are unitless. The run therefore reports `min=85.852, max=89.989, mean=89.928` degrees for a smooth placeholder surface. Add a documented metric Mars coordinate conversion or use a metric/projected placeholder before treating these values as meaningful hazard results.
- `scripts/slope.py:6` uses `from config import ...`, so importing the file as `scripts.slope` fails with `ModuleNotFoundError: No module named 'config'`; the direct documented command works because Python puts `scripts/` on `sys.path`. Use an import pattern that supports both CLI execution and test/module reuse.
- `docs/STATUS.md:3-12` and `README.md:8-9` accurately show the pipeline is incomplete, but the branch still has no route planner, Leaflet map, three NASA data layers, safety panel, science targets, or obstacle-avoiding route required by the challenge and plan. This slope branch is an incremental processing step, not an MVP-ready application.

## Nice to have

- `README.md:13-16` says to create and activate a virtual environment but does not show the actual commands; add a concrete, copy-pasteable example.
- `requirements.txt:1-2` leaves `rasterio` and `numpy` unpinned, reducing reproducibility.

Validation performed:

- `python scripts/make_placeholder_data.py`: succeeded and printed `Wrote placeholder DEM: /home/livio/repos/martian/data/processed/dem.tif`.
- `python scripts/slope.py`: succeeded and printed `Slope degrees: min=85.852, max=89.989, mean=89.928`.
- Halving both DEM cell sizes changed the slope array (`array_equal=False`; mean difference about `0.0361`), confirming the raster resolution is read from the file rather than hardcoded.
- `slope.tif` and `hazard.tif` retained the DEM's `crs=None`, bounds, and resolution. Both contain explicit placeholder metadata; hazard metadata defines `0=walkable, 1=over max slope, 255=nodata`.
- The threshold is imported from `MAX_WALKABLE_SLOPE_DEG` at `scripts/slope.py:6` and applied at line 35.
- The largest committed file is `data/processed/dem.tif` at 17,328 bytes; no `data/raw/` files are tracked.

**Merge readiness:** Not ready to merge until the nodata contamination and degree-variable naming issues are fixed. Even afterward, the branch remains an incremental slope-processing step and does not satisfy the full challenge MVP.
