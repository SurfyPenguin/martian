"""Create small, real-data context layers from the supplied raw rasters.

This is the only script allowed to read data/raw/. It deliberately reads
decimated arrays and never loads either source raster at full resolution.
"""

import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling
from rasterio.windows import Window, bounds as window_bounds, from_bounds


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_DIR = PROJECT_ROOT / "web" / "data"
TARGET_WIDTH = 2000
MAX_OUTPUT_BYTES = 3 * 1024 * 1024


def raster_bounds(path: Path) -> dict[str, float]:
    with rasterio.open(path) as source:
        return {
            "min_lon": source.bounds.left,
            "min_lat": source.bounds.bottom,
            "max_lon": source.bounds.right,
            "max_lat": source.bounds.top,
        }


def decimated_shape(width: float, height: float) -> tuple[int, int]:
    height = max(1, round(height * TARGET_WIDTH / width))
    return height, TARGET_WIDTH


def scale_to_rgba(values: np.ndarray, valid: np.ndarray) -> np.ndarray:
    rgba = np.zeros((*values.shape, 4), dtype=np.uint8)
    if not np.any(valid):
        return rgba
    minimum = float(values[valid].min())
    maximum = float(values[valid].max())
    if minimum == maximum:
        scaled = np.full(values.shape, 127, dtype=np.uint8)
    else:
        scaled = np.clip(
            (values - minimum) / (maximum - minimum) * 255,
            0,
            255,
        )
        scaled = np.nan_to_num(scaled, nan=0).astype(np.uint8)
    rgba[..., :3] = scaled[..., None]
    rgba[..., 3] = np.where(valid, 255, 0)
    return rgba


def write_overview(
    path: Path,
    output: Path,
    *,
    resampling: Resampling,
    bounds: dict[str, float] | None = None,
) -> dict[str, float]:
    with rasterio.open(path) as source:
        window = (
            from_bounds(
                bounds["min_lon"],
                bounds["min_lat"],
                bounds["max_lon"],
                bounds["max_lat"],
                source.transform,
            )
            if bounds
            else Window(0, 0, source.width, source.height)
        )
        if (
            window.col_off < 0
            or window.row_off < 0
            or window.col_off + window.width > source.width
            or window.row_off + window.height > source.height
        ):
            raise ValueError(f"Requested overview bounds are outside {path}")
        height, width = decimated_shape(window.width, window.height)
        values = source.read(
            1,
            out_shape=(height, width),
            window=window,
            resampling=resampling,
            masked=True,
        )
        valid = ~values.mask if np.ma.isMaskedArray(values) else np.ones(values.shape, dtype=bool)
        if np.ma.isMaskedArray(values):
            data = np.asarray(values.astype("float32").filled(np.nan), dtype="float32")
        else:
            data = np.asarray(values, dtype="float32")
        left, bottom, right, top = window_bounds(window, source.transform)
    write_rgba_png(output, scale_to_rgba(data, valid & np.isfinite(data)))
    return {
        "min_lon": left,
        "min_lat": bottom,
        "max_lon": right,
        "max_lat": top,
    }


def write_rgba_png(path: Path, rgba: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".webp":
        Image.fromarray(rgba, mode="RGBA").save(path, format="WEBP", quality=88, method=6)
    else:
        Image.fromarray(rgba, mode="RGBA").save(path, optimize=True, compress_level=9)
    size = path.stat().st_size
    print(f"{path.relative_to(PROJECT_ROOT)}: {size / 1024:.1f} KiB")
    if size > MAX_OUTPUT_BYTES:
        raise RuntimeError(f"{path} exceeds the 3 MiB backdrop limit")


def create_hillshade(output: Path) -> None:
    source = RAW_DIR / "gale_dem_smg_1m.tif"
    with tempfile.TemporaryDirectory(prefix="martian-map-backdrop-") as temp_dir:
        temp_dir_path = Path(temp_dir)
        decimated_dem = temp_dir_path / "dem_decimated.tif"
        hillshade = temp_dir_path / "hillshade.tif"
        with rasterio.open(source) as dataset:
            height, width = decimated_shape(dataset.width, dataset.height)
        subprocess.run(
            [
                "gdal_translate",
                "-of",
                "GTiff",
                "-outsize",
                str(width),
                str(height),
                "-r",
                "average",
                str(source),
                str(decimated_dem),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        subprocess.run(
            [
                "gdaldem",
                "hillshade",
                "-s",
                "59157",
                "-compute_edges",
                str(decimated_dem),
                str(hillshade),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        write_overview(hillshade, output, resampling=Resampling.nearest)


def main() -> None:
    ctx_path = RAW_DIR / "gale_ctx_blockadj_dd.tif"
    dem_path = RAW_DIR / "gale_dem_smg_1m.tif"
    ctx_output = OUTPUT_DIR / "backdrop_ctx.webp"
    hillshade_output = OUTPUT_DIR / "backdrop_hillshade.webp"

    dem_bounds = raster_bounds(dem_path)
    ctx_bounds = write_overview(
        ctx_path,
        ctx_output,
        resampling=Resampling.average,
        bounds=dem_bounds,
    )
    create_hillshade(hillshade_output)
    backdrop = {
        "data_status": "REAL NASA data - lower-resolution surrounding context only",
        "center": {},
        "layers": {
            "imagery": {
                "path": "web/data/backdrop_ctx.webp",
                "bounds": ctx_bounds,
            },
            "hillshade": {
                "path": "web/data/backdrop_hillshade.webp",
                "bounds": dem_bounds,
            },
        },
    }
    bounds = [layer["bounds"] for layer in backdrop["layers"].values()]
    backdrop["center"] = {
        "lat": (min(item["min_lat"] for item in bounds)
                + max(item["max_lat"] for item in bounds)) / 2,
        "lon": (min(item["min_lon"] for item in bounds)
                + max(item["max_lon"] for item in bounds)) / 2,
    }
    (OUTPUT_DIR / "backdrop.json").write_text(json.dumps(backdrop, indent=2) + "\n")
    print(f"{OUTPUT_DIR.relative_to(PROJECT_ROOT) / 'backdrop.json'}: written")


if __name__ == "__main__":
    main()
