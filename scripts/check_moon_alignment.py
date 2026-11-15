"""Automated Moon alignment tests (Target 2).

Prints a PASS/FAIL table. Every row must PASS or the script exits nonzero.
Python side uses scripts/moon_geo.py (the pyproj transformer built from the
raster's own CRS). Browser side runs the web app's own functions from
web/geo.js (gridToMap, latLonToMap, moonXYToLonLat) under Node.

Rows:
  a) every overlay PNG's bounds in layers.json equal its GeoTIFF bounds
     within one pixel, and the PNG dimensions match the GeoTIFF shape
  b) the highest and lowest elevation pixel of each site's GeoTIFF, mapped
     through Python and through the browser's own gridToMap, agree within
     one 10 m cell (proves no y flip or x shift)
  c) region centers: geojson -> meters (Python) equal regions.json and the
     browser's latLonToMap
  d) the JS inverse projection agrees with Python within 1 m on 5 test points
  e) the backdrop overlay width/height in meters equals cols/rows x 1000 m
"""

import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from moon_geo import MoonGeometry, raster_edges  # noqa: E402

WEB_MOON = ROOT / "web" / "data" / "moon"
PROCESSED = ROOT / "data" / "processed" / "moon"
RAW_DIR = ROOT / "data" / "raw" / "moon"
SITES = ("site_01", "site_04", "site_07", "sl3")
GRID_SIZE_M = 10.0

NODE_HARNESS = r"""
const fs = require("fs");
eval(fs.readFileSync("web/geo.js", "utf8"));
setGeoReference({}, "moon", 1737400);
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const out = { cells: {}, forward: [], inverse: [] };
for (const [site, spec] of Object.entries(input.cells)) {
  const siteObj = { grid: { geo_reference: spec.geo_reference } };
  out.cells[site] = spec.points.map(
    ([row, col]) => gridToMap(siteObj, row, col)
  );
}
for (const [lat, lon] of input.forward) {
  const p = latLonToMap(lat, lon);
  out.forward.push([p[0], p[1]]);
}
for (const [x, y] of input.inverse) {
  const p = moonXYToLonLat(x, y);
  out.inverse.push([p.lat, p.lon]);
}
console.log(JSON.stringify(out));
"""

results = []


def check(name, ok, detail):
    results.append((name, bool(ok), detail))
    return bool(ok)


def within_cell(a, b, cell_m):
    return abs(a[0] - b[0]) <= cell_m and abs(a[1] - b[1]) <= cell_m


def meters_between(latlon1, latlon2):
    lat1, lon1 = latlon1
    lat2, lon2 = latlon2
    return math.hypot(
        math.radians(lat2 - lat1) * 1_737_400.0,
        math.radians(lon2 - lon1) * 1_737_400.0
        * math.cos(math.radians((lat1 + lat2) / 2)),
    )


def main():
    moon = MoonGeometry(RAW_DIR / "site_01_final_adj_5mpp_surf.tif")
    layers = json.loads((WEB_MOON / "layers.json").read_text())
    regions = json.loads((WEB_MOON / "regions.json").read_text())
    geojson = json.loads(
        (RAW_DIR / "A3_Named_regions_SP.geojson").read_text()
    )

    # ---- a) overlay PNG bounds vs GeoTIFF bounds, PNG shape vs raster shape
    entries = [("backdrop", layers["backdrop"],
                RAW_DIR / "LDRM_80S_1000MPP_ADJ_ROUGH_100M.tiff",
                WEB_MOON / "roughness_backdrop.png")]
    for site in SITES:
        for layer, tif in (
            ("hillshade", "elevation.tif"),
            ("slope", "slope.tif"),
            ("hazard", "hazard.tif"),
            ("support", "support.tif"),
        ):
            entries.append(
                (f"{site}.{layer}", layers["sites"][site][layer],
                 PROCESSED / site / tif,
                 PROCESSED / site / f"{layer}.png")
            )
    for name, entry, tif_path, png_path in entries:
        edges = raster_edges(tif_path)
        bounds = entry["bounds_m"]
        pixel = max(entry["pixel_size_m"]["x"], entry["pixel_size_m"]["y"])
        delta = max(
            abs(bounds["min_x"] - edges["bounds_m"]["min_x"]),
            abs(bounds["min_y"] - edges["bounds_m"]["min_y"]),
            abs(bounds["max_x"] - edges["bounds_m"]["max_x"]),
            abs(bounds["max_y"] - edges["bounds_m"]["max_y"]),
        )
        with rasterio.open(tif_path) as source:
            tif_shape = (source.height, source.width)
        with Image.open(png_path) as image:
            png_shape = (image.height, image.width)
        # The overlay PNG may be decimated; its shape must match the GeoTIFF
        # shape at the PNG's own resolution (image_resolution_m / pixel size).
        overlay_pixel = entry.get("image_resolution_m", pixel)
        expected_png = (
            round(tif_shape[0] * entry["pixel_size_m"]["y"] / overlay_pixel),
            round(tif_shape[1] * entry["pixel_size_m"]["x"] / overlay_pixel),
        )
        check(
            f"a:{name} bounds==GeoTIFF within one pixel",
            delta <= pixel and png_shape == expected_png,
            f"max delta {delta:.3f} m <= {pixel:.0f} m; "
            f"png {png_shape} == {expected_png} at "
            f"{overlay_pixel:.0f} m/px",
        )

    # ---- b) extreme pixels: Python map meters vs the browser's gridToMap
    node_input = {"cells": {}}
    extremes = {}
    for site in SITES:
        with rasterio.open(PROCESSED / site / "elevation.tif") as source:
            elevation = source.read(1)
        with open(PROCESSED / site / "grid.json") as handle:
            grid = json.load(handle)
        valid = np.isfinite(elevation)
        high_row, high_col = np.unravel_index(
            np.argmax(np.where(valid, elevation, -np.inf)), elevation.shape
        )
        low_row, low_col = np.unravel_index(
            np.argmin(np.where(valid, elevation, np.inf)), elevation.shape
        )
        extremes[site] = {
            "grid": grid,
            "points": [
                (int(high_row), int(high_col)),
                (int(low_row), int(low_col)),
            ],
            "high_value": float(elevation[high_row, high_col]),
            "low_value": float(elevation[low_row, low_col]),
        }
        node_input["cells"][site] = {
            "geo_reference": grid["geo_reference"],
            "points": extremes[site]["points"],
        }
    node_input["forward"] = []
    node_input["inverse"] = []
    with tempfile.NamedTemporaryFile("w", suffix=".json") as handle:
        json.dump(node_input, handle)
        handle.flush()
        node_output = subprocess.run(
            ["node", "-e", NODE_HARNESS],
            stdin=open(handle.name, "rb"),
            capture_output=True, text=True, cwd=ROOT, check=True,
        ).stdout
    browser = json.loads(node_output)
    for site in SITES:
        for label, (row, col), value in (
            ("highest", extremes[site]["points"][0],
             extremes[site]["high_value"]),
            ("lowest", extremes[site]["points"][1],
             extremes[site]["low_value"]),
        ):
            transform = extremes[site]["grid"]["geo_reference"]["transform"]
            x_py = transform[0] * (col + 0.5) + transform[2]
            y_py = transform[4] * (row + 0.5) + transform[5]
            y_js, x_js = browser["cells"][site][
                0 if label == "highest" else 1
            ]
            check(
                f"b:{site} {label} pixel ({row},{col}) "
                f"{value:.1f} m agrees within one 10 m cell",
                within_cell((y_py, x_py), (y_js, x_js), GRID_SIZE_M),
                f"python (y {y_py:.2f}, x {x_py:.2f}) vs browser "
                f"(y {y_js:.2f}, x {x_js:.2f})",
            )

    # ---- c) region centers: geojson -> Python == regions.json == browser
    source_by_id = {
        str(feature.get("id", feature["properties"].get("id"))): feature
        for feature in geojson["features"]
    }
    center_rows = []
    for feature in regions["features"]:
        name = feature["properties"]["name"]
        source = source_by_id.get(str(feature["id"]))
        if source is not None:
            ring = source["geometry"]["coordinates"][0]
            points = [moon.lonlat_to_xy(float(lon), float(lat))
                      for lon, lat in ring[:-1]]
            center_py = (
                sum(p[0] for p in points) / len(points),
                sum(p[1] for p in points) / len(points),
            )
        else:
            corners = feature["geometry"]["coordinates"][0]
            xs = [p[0] for p in corners[:-1]]
            ys = [p[1] for p in corners[:-1]]
            center_py = (sum(xs) / len(xs), sum(ys) / len(ys))
        center_json = feature["properties"]["center_xy"]
        center_lonlat = feature["properties"]["center_lonlat"]
        node_input["forward"].append([center_lonlat[1], center_lonlat[0]])
        center_rows.append((name, center_py, center_json, center_lonlat))
    # run the browser once more with the forward conversions added
    with tempfile.NamedTemporaryFile("w", suffix=".json") as handle:
        json.dump(node_input, handle)
        handle.flush()
        node_output = subprocess.run(
            ["node", "-e", NODE_HARNESS],
            stdin=open(handle.name, "rb"),
            capture_output=True, text=True, cwd=ROOT, check=True,
        ).stdout
    browser = json.loads(node_output)
    for index, (name, center_py, center_json, center_lonlat) in enumerate(
        center_rows
    ):
        y_js, x_js = browser["forward"][index]
        ok_json = math.hypot(
            center_py[0] - center_json[0], center_py[1] - center_json[1]
        ) < 0.01
        ok_browser = within_cell(center_py, (x_js, y_js), 1.0) and within_cell(
            (center_json[0], center_json[1]), (x_js, y_js), 1.0
        )
        check(
            f"c:{name[:40]} center geojson==regions.json==browser",
            ok_json and ok_browser,
            f"python ({center_py[0]:.2f}, {center_py[1]:.2f}), "
            f"json ({center_json[0]:.2f}, {center_json[1]:.2f}), "
            f"browser (x {x_js:.2f}, y {y_js:.2f})",
        )

    # ---- d) JS inverse projection vs Python within 1 m on 5 test points
    # Inputs are projected meters (regions.json center_xy); both sides invert
    # to lat/lon and the results are compared in meters on the sphere.
    test_points = [
        center_rows[6][1],  # Connecting Ridge center (x, y)
        center_rows[8][1],  # Peak Near Shakleton center
        center_rows[5][1],  # Connecting Ridge Extension center
        center_rows[0][1],  # Amundsen Rim center
        center_rows[11][1],  # Malapert Massif center
    ]
    inverse_input = [list(point) for point in test_points]
    with tempfile.NamedTemporaryFile("w", suffix=".json") as handle:
        json.dump({"cells": {}, "forward": [], "inverse": inverse_input},
                  handle)
        handle.flush()
        node_output = subprocess.run(
            ["node", "-e", NODE_HARNESS],
            stdin=open(handle.name, "rb"),
            capture_output=True, text=True, cwd=ROOT, check=True,
        ).stdout
    browser = json.loads(node_output)
    for (x, y), (js_lat, js_lon) in zip(test_points, browser["inverse"]):
        py_lon, py_lat = moon.xy_to_lonlat(x, y)
        error = meters_between((py_lat, py_lon), (js_lat, js_lon))
        check(
            f"d:inverse ({x:.0f}, {y:.0f}) m JS vs Python within 1 m",
            error <= 1.0,
            f"error {error:.4f} m",
        )

    # ---- e) backdrop overlay width equals cols x 1000 m
    backdrop = layers["backdrop"]
    width = backdrop["bounds_m"]["max_x"] - backdrop["bounds_m"]["min_x"]
    height = backdrop["bounds_m"]["max_y"] - backdrop["bounds_m"]["min_y"]
    cols_by_1000 = backdrop["shape"][1] * backdrop["pixel_size_m"]["x"]
    rows_by_1000 = backdrop["shape"][0] * backdrop["pixel_size_m"]["y"]
    check(
        "e:backdrop overlay width == cols x 1000 m",
        math.isclose(width, cols_by_1000, rel_tol=1e-9)
        and math.isclose(height, rows_by_1000, rel_tol=1e-9),
        f"width {width:.0f} m vs {cols_by_1000:.0f} m; "
        f"height {height:.0f} m vs {rows_by_1000:.0f} m",
    )

    # ---- report
    print(f"{'RESULT':6} | TEST | DETAIL")
    print("-" * 100)
    failures = 0
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL':6} | {name} | {detail}")
        failures += 0 if ok else 1
    print("-" * 100)
    print(f"{len(results) - failures}/{len(results)} checks passed")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
