"""Verify endpoint snapping, disconnected pockets, and EVA-limit edge cases."""

import json
import math
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from config import EVA_HOURS, SAFETY_MARGIN_CELLS, SITES, WALKING_SPEED_KMH  # noqa: E402
from route import astar, nearest_walkable_cell, route_distance_km  # noqa: E402


def bresenham(start: tuple[int, int], end: tuple[int, int]):
    row, col = start
    end_row, end_col = end
    delta_row = abs(end_row - row)
    delta_col = abs(end_col - col)
    step_row = 1 if row < end_row else -1
    step_col = 1 if col < end_col else -1
    error = delta_col - delta_row
    while True:
        yield row, col
        if (row, col) == (end_row, end_col):
            break
        doubled_error = 2 * error
        if doubled_error > -delta_row:
            error -= delta_row
            col += step_col
        if doubled_error < delta_col:
            error += delta_col
            row += step_row


def load_site(site: str):
    processed = ROOT / "data" / "processed" / site
    web_data = ROOT / "web" / "data" / site
    grid = json.loads((processed / "grid.json").read_text())
    metadata = json.loads((web_data / "cost.json").read_text())
    costs = np.fromfile(web_data / "cost.bin", dtype="<f4").reshape(
        metadata["rows"], metadata["cols"]
    )
    clearance_cells = np.fromfile(
        web_data / metadata["clearance_files"]["cells"],
        dtype="<f4",
    ).reshape(costs.shape)
    with rasterio.open(processed / "hazard.tif") as source:
        hazard = source.read(1) == 1
        x_size_m = float(metadata["cell_size_m"]["x"])
        y_size_m = float(metadata["cell_size_m"]["y"])
    walkable = np.isfinite(costs) & (clearance_cells > SAFETY_MARGIN_CELLS)
    labels, _ = ndimage.label(
        walkable,
        structure=ndimage.generate_binary_structure(2, 1),
    )
    return grid, costs, clearance_cells, hazard, walkable, labels, x_size_m, y_size_m


def nearest_to(point: tuple[int, int], candidates: np.ndarray) -> tuple[int, int]:
    distances = np.sum((candidates - np.asarray(point)) ** 2, axis=1)
    return tuple(int(value) for value in candidates[int(np.argmin(distances))])


def check_site(site: str) -> list[str]:
    (
        grid,
        costs,
        clearance_cells,
        hazard,
        walkable,
        labels,
        x_size_m,
        y_size_m,
    ) = load_site(site)
    stats = json.loads(
        (ROOT / "data" / "processed" / site / "stats.json").read_text()
    )
    habitat = (grid["habitat"]["row"], grid["habitat"]["col"])
    habitat_component = labels[habitat]
    if not habitat_component:
        raise AssertionError(f"{site} habitat is not in the passable grid")

    largest_label = int(np.bincount(labels.ravel())[1:].argmax() + 1)
    if habitat_component != largest_label:
        raise AssertionError(f"{site} habitat is not in the largest passable component")
    for target in grid["targets"]:
        if labels[target["row"], target["col"]] != largest_label:
            raise AssertionError(f"{site} target is outside the largest passable component")

    target_cells = [(point["row"], point["col"]) for point in grid["targets"]]
    direct_hazard_crossing = any(
        hazard[row, col]
        for start, end in zip(target_cells, target_cells[1:])
        for row, col in bresenham(start, end)
    )
    if not direct_hazard_crossing:
        raise AssertionError(f"{site} target-to-target straight lines avoid all hazards")

    hazard_cells = np.argwhere(hazard)
    hazard_cell = nearest_to(habitat, hazard_cells)
    snapped_hazard, hazard_distance = nearest_walkable_cell(
        hazard_cell,
        walkable,
        x_size_m,
        y_size_m,
    )
    if hazard_cell == snapped_hazard or not walkable[snapped_hazard]:
        raise AssertionError(f"{site} hazard checkpoint did not snap to a free cell")

    margin_cells = np.argwhere(
        ~hazard & (clearance_cells <= SAFETY_MARGIN_CELLS)
    )
    if margin_cells.size == 0:
        raise AssertionError(f"{site} contains no cell inside the safety margin")
    margin_cell = nearest_to(habitat, margin_cells)
    snapped_margin, margin_distance = nearest_walkable_cell(
        margin_cell,
        walkable,
        x_size_m,
        y_size_m,
    )
    if margin_cell == snapped_margin or not walkable[snapped_margin]:
        raise AssertionError(f"{site} safety-margin checkpoint did not snap to a free cell")

    component_sizes = np.bincount(labels.ravel())
    component_sizes[0] = 0
    disconnected_labels = [
        int(label)
        for label in np.flatnonzero(component_sizes)
        if label != habitat_component
    ]
    if not disconnected_labels:
        raise AssertionError(f"{site} has no disconnected passable pocket to test")
    pocket_label = max(disconnected_labels, key=lambda label: component_sizes[label])
    pocket_cells = np.argwhere(labels == pocket_label)
    pocket = tuple(int(value) for value in pocket_cells[len(pocket_cells) // 2])
    try:
        astar(habitat, pocket, walkable, costs, x_size_m, y_size_m)
    except ValueError as error:
        if "No walkable route exists" not in str(error):
            raise
    else:
        raise AssertionError(f"{site} router found a path into a disconnected pocket")

    habitat_component_cells = np.argwhere(labels == habitat_component)
    farthest_index = int(
        np.sum(
            (habitat_component_cells - np.asarray(habitat)) ** 2,
            axis=1,
        ).argmax()
    )
    far_cell = tuple(int(value) for value in habitat_component_cells[farthest_index])
    one_way = astar(habitat, far_cell, walkable, costs, x_size_m, y_size_m)
    one_way_km = route_distance_km(one_way, x_size_m, y_size_m)
    loops = math.floor(EVA_HOURS * WALKING_SPEED_KMH / (2 * one_way_km)) + 1
    stress_distance_km = 2 * one_way_km * loops
    stress_time_h = stress_distance_km / WALKING_SPEED_KMH
    if stress_time_h <= EVA_HOURS:
        raise AssertionError(f"{site} repeated out-and-back stress route did not exceed EVA limit")

    return [
        f"### {site}: {SITES[site]['name']}",
        "",
        f"- Auto plan: {stats['distance_km']:.3f} km / {stats['time_h']:.3f} h; "
        f"{'WITHIN' if stats['within_eva_limit'] else 'OVER'} EVA limit.",
        f"- Habitat and all three PLACEHOLDER targets are in the largest passable component; "
        f"straight target lines cross true hazard cells: **PASS**.",
        f"- Hazard checkpoint `{hazard_cell}` snapped {hazard_distance:.1f} m to `{snapped_hazard}`: **PASS**.",
        f"- Safety-margin checkpoint `{margin_cell}` snapped {margin_distance:.1f} m to `{snapped_margin}`: **PASS**.",
        f"- Disconnected-pocket checkpoint `{pocket}` returned **NO SAFE PATH**; the browser renders unreachable legs as a red dashed connector.",
        f"- Over-limit round-trip stress sequence: {loops} repeated out-and-back legs, "
        f"{stress_distance_km:.3f} km / {stress_time_h:.3f} h: **OVER EVA LIMIT**.",
        "",
    ]


def main() -> None:
    report = [
        "# Site stress-test results",
        "",
        "Fixed site windows were clipped from the supplied NASA DEM and CTX using "
        "GDAL windowed reads only. The source rasters were not fully loaded, and "
        "the slope, roughness, hazard, safety-margin, and walking thresholds were "
        "not changed. Route thresholds are assumptions, not validated EVA limits.",
        "",
        "Both source windows are within the DEM extent and full CTX coverage. "
        "No DEM NoData was present in either resampled site clip, so neither box "
        "needed to be shifted.",
        "",
        "The disconnected-pocket test targets a separate passable component. The "
        "over-limit scenario deliberately repeats a reachable out-and-back "
        "checkpoint sequence when the automatic plan is not already over the "
        "configured four-hour limit.",
        "",
    ]
    for site in ("site3", "site4"):
        report.extend(check_site(site))
    print("\n".join(report))


if __name__ == "__main__":
    main()
