# Review: feat/setup

## Must fix

- `data/README.md:2-4` records specific coordinates as sourced from “Mars Trek” but leaves the date blank and does not label the values as placeholders. The listed box (`-4.9105` to `-4.24672`, `137.36136` to `137.95757`) is also inconsistent with the roughly 5 x 5 km bounds derived in `scripts/config.py`. Remove these unsupported NASA-looking values or document a verified source/date and make the bounds consistent. This violates the project rule against invented data or numbers.

## Should fix

- `scripts/make_placeholder_data.py:39-48` writes a geographic transform but no CRS or coordinate-convention metadata. Downstream raster processing could interpret the DEM incorrectly; add an explicit, documented Mars coordinate convention or make the absence of a CRS clear to consumers.
- `docs/STATUS.md:9-12` still defines the slope/route pipeline and web app as the definition of done, but neither `scripts/slope.py`, `scripts/route.py`, nor `web/index.html` exists on this branch. Running `python scripts/slope.py && python scripts/route.py` produced: `python: can't open file '/home/livio/repos/martian/scripts/slope.py': [Errno 2] No such file or directory`. The generator itself succeeded and wrote `data/processed/dem.tif` as a 64 x 64 float32 GeoTIFF with tags `DATA_STATUS=PLACEHOLDER - synthetic DEM, not NASA data` and `DESCRIPTION=Synthetic elevation surface for local pipeline development`.
- `README.md:8-17` documents only placeholder DEM setup. It does not claim to run the full planner, but the project remains far from the challenge requirements: no three layered NASA data types, safety panel, science targets, or obstacle-avoiding route are implemented yet.

## Nice to have

- `requirements.txt:1-2` leaves `rasterio` and `numpy` unpinned, which makes the setup less reproducible across environments.
- Add trailing newlines to the changed text files for cleaner diffs.

**Merge readiness:** Not ready to merge until the unsupported/inconsistent AOI record is corrected or removed. Even after that, this is only an incremental setup branch and does not yet satisfy the Martian Map MVP definition of done.
