"""Inspect the real processed site rasters and regenerate DATA_SCHEMA.md."""

from pathlib import Path

import rasterio

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
SCHEMA_PATH = ROOT / "docs" / "DATA_SCHEMA.md"


def describe(path: Path) -> dict:
    with rasterio.open(path) as source:
        return {
            "path": str(path.relative_to(ROOT)),
            "shape": f"{source.height} x {source.width}",
            "bands": source.count,
            "dtype": ", ".join(source.dtypes),
            "crs": str(source.crs),
            "nodata": source.nodata,
            "bounds": tuple(round(value, 10) for value in source.bounds),
            "resolution": tuple(round(value, 10) for value in source.res),
            "size": path.stat().st_size,
        }


def main() -> None:
    paths = sorted(PROCESSED.glob("site*_dem.tif"))
    if not paths:
        raise FileNotFoundError("No site*_dem.tif files found in data/processed/")
    rows = []
    for dem_path in paths:
        site = dem_path.stem.removesuffix("_dem")
        for path in (dem_path, PROCESSED / f"{site}_imagery.tif"):
            if not path.exists():
                rows.append(f"| `{path.name}` | missing |")
                continue
            info = describe(path)
            rows.append(
                f"| `{info['path']}` | {info['shape']} | {info['bands']} | "
                f"{info['dtype']} | `{info['crs']}` | `{info['nodata']}` | "
                f"`{info['bounds']}` | `{info['resolution']}` | "
                f"{info['size']:,} bytes |"
            )
            print(
                f"{info['path']}: {info['shape']}, {info['dtype']}, "
                f"CRS={info['crs']}, nodata={info['nodata']}, "
                f"cell={info['resolution']}"
            )
    SCHEMA_PATH.write_text(
        "# Real input data schema\n\n"
        "These files are the clipped real inputs used by the site pipeline. "
        "The site coordinates in `scripts/config.py` remain explicitly labeled "
        "placeholders until mission points are supplied.\n\n"
        "| File | Shape | Bands | Dtype | CRS | NoData | Bounds "
        "(left, bottom, right, top) | Resolution (x, y) | Size |\n"
        "|---|---:|---:|---|---|---:|---|---|---:|\n"
        + "\n".join(rows)
        + "\n\n"
        "DEM values are elevation in meters. DEM NoData is treated as impassable; "
        "slope is never computed across invalid neighborhoods. Imagery is CTX "
        "single-band raster data and is resampled to each site's DEM grid for "
        "the browser overlay.\n"
    )
    print(f"Wrote {SCHEMA_PATH}")


if __name__ == "__main__":
    main()
