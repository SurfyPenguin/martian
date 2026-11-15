# Martian Map

Martian Map is an interactive route-planning prototype with Mars and Moon
modes. It was built for the 2026 NASA Space Apps Challenge and its
"Interplanetary Survival Guide: Martian Map" challenge.

Mars mode combines NASA-provided CTX imagery and elevation data with derived
slope, roughness, and route information. Moon mode uses supplied NASA lunar
surface, slope, roughness, and LOLA return-count products. Habitat and
science-target coordinates are placeholders. This is a demonstration project,
not an operational navigation or astronaut-safety system.

## Run the map

The repository includes the processed site data and small web map assets needed
for the demo. From the repository root, start a local server:

```bash
python3 -m http.server 8000
```

Open [http://localhost:8000/web/](http://localhost:8000/web/) in a browser.
Serve the repository over HTTP; opening `web/index.html` directly as a file
does not provide the data paths the app needs. The web app uses plain
HTML, JavaScript, and Leaflet. It has no JavaScript build step.

## Install Python tools and rebuild data

Python 3.11 or newer is required for the processing scripts. From the
repository root, create an environment and install the listed dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

To regenerate the site slope, hazard, and route outputs from the clipped inputs
in `data/processed/`, run:

```bash
python scripts/slope.py --site site1
python scripts/route.py --site site1
python scripts/slope.py --site site2
python scripts/route.py --site site2
python scripts/slope.py --site site3
python scripts/route.py --site site3
python scripts/slope.py --site site4
python scripts/route.py --site site4
```

Moon mode's committed outputs run without the raw source files. To regenerate
them, place the listed Moon inputs in `data/raw/moon/` and process one site at
a time:

```bash
python scripts/make_moon_site.py --site site_01
python scripts/make_moon_site.py --site site_04
python scripts/make_moon_site.py --site site_07
python scripts/make_moon_site.py --site sl3
```

The Moon surface and slope sources are 5 m rasters; the routing grid is 10 m.
The low-resolution LOLA roughness backdrop is context only, while the
5 m LOLA count layer shows where recorded returns exist. Do not load the large
LOLA count raster or any other source raster in full.

To regenerate the low-resolution surrounding map, install the GDAL command-line
tools (`gdal_translate` and `gdaldem`) and place the supplied NASA source files
in the git-ignored `data/raw/` directory:

- `gale_ctx_blockadj_dd.tif`
- `gale_dem_smg_1m.tif`

For Ubuntu or Debian, the command-line tools are provided by `gdal-bin`:

```bash
sudo apt install gdal-bin
python scripts/make_backdrop.py
```

The source rasters are large, approximately 1.8 GB for CTX and 5.8 GB for the
DEM. The backdrop script reads them at reduced resolution; do not load the
full rasters into memory. The raw files are not included in the repository.
The existing small backdrop assets in `web/data/` are sufficient to run the
demo without them.

## Use the map

Choose Mars or Moon at the top of the sidebar. In Mars mode, choose a site from
the data-driven selector: **Gale crater floor**,
**Southern box**, **Rough terrain box**, or **Dune-edge box**. Use
the layer controls to show elevation, CTX imagery, slope, hazards, routes, or
targets. The surrounding map is lower-resolution context only; route planning
is available only inside the four site areas.

Moon mode provides four south-pole planning windows: Connecting Ridge,
`site_04` raster (an unmatched raster, not a confirmed named region), Peak Near
Shakleton, and Connecting Ridge Extension. Its layers show hillshade, slope,
hazards, LOLA return support, and the low-resolution roughness backdrop. Most
5 m elevation pixels are interpolated; the support layer marks locations with
recorded LOLA returns. Slope uncertainty is roughly 1.5 to 2.5 degrees. Lunar
imagery, illumination, temperature, and radiation are not integrated, and
lunar radiation dose is not computed.

The Moon source products are `LDRM_80S_1000MPP_ADJ_ROUGH_100M.tiff`
(1,000 m/pixel roughness), `LRO_LOLA_Count_SPole875_5mp_v04.tif` (5 m/pixel
return counts), and the supplied `site_01`, `site_04`, `site_07`, and `sl3`
surface (`_surf.tif`) and slope (`_slp.tif`) rasters (5 m source resolution).

Select **Add checkpoint**, then click inside the active site to add a stop.
Drag stops to move them, or use the checkpoint controls to undo, clear, or
restore the automatic plan. The optional return-to-Habitat setting includes
the return leg in route calculations. Manually added checkpoints remain only
for the current page session.

The routing controls provide A*, Dijkstra, and Weighted A* algorithms, plus
Fastest, Safer, and Alternate route choices when valid alternatives are
available. Hazard cells and the configured safety margin are blocked. A
checkpoint placed too close to a hazard is moved to a nearby available cell
and reported in the interface.

## Data and planning limits

The CTX imagery, DEM, LOLA roughness, LOLA return-count, and supplied lunar
surface and slope inputs used by this project are NASA data and remain NASA's
data. The repository does not record their product IDs or acquisition dates.
The project is an independent challenge prototype and is not an official NASA
product.

| Map information | What it shows | Source and status |
|---|---|---|
| CTX imagery | Optical surface imagery for each site | NASA-provided imagery in `data/processed/site1_imagery.tif` through `site4_imagery.tif`, resampled and scaled per site |
| DEM elevation | Surface elevation in meters | NASA-provided digital elevation models in `data/processed/site1_dem.tif` through `site4_dem.tif`; the processed site grids are about 10 m per cell |
| Slope and roughness hazards | Areas blocked for route planning | Calculated from the DEM; not a separate NASA measurement |
| Surrounding map | Lower-resolution CTX imagery and DEM hillshade | Derived from NASA source rasters; context only, with no route data |
| Routes and science targets | Candidate paths between the habitat and stops | Routes are calculated by the planner; habitat and target coordinates are placeholders |
| Lunar roughness backdrop | Regional south-pole context | NASA LOLA roughness product at 1,000 m/pixel; context only |
| Lunar elevation and slope | Site terrain at 10 m routing resolution | NASA-provided 5 m surface and slope rasters, resampled for the planner |
| LOLA return support | Cells with at least one recorded laser return | NASA LOLA count product at 5 m/pixel; support is sparse and does not mean every surface pixel was measured |

The current app does not provide mineral identifications or live radiation
and weather measurements. Mars dose is an estimate based on an assumption,
not a live or mission-validated radiation dataset. Moon dose is not computed.

The route planner uses these adjustable settings from `scripts/config.py`:

- EVA duration limit: 4 hours for the planned round trip.
- Walking speed: 3 km/h.
- Estimated radiation dose rate: 0.02 mSv per hour.
- Maximum walkable slope: 15 degrees.
- Maximum local roughness: 15 m standard deviation in a 5 by 5 cell area.
- Default hazard safety margin: 2 cells, adjustable in the interface.

These are planning assumptions, not validated Mars suit, crew, or mission
limits. A route is labeled **WITHIN EVA LIMIT** when its estimated time is at
or below the configured duration; otherwise it is labeled **OVER EVA LIMIT**.
The route estimate includes the return to Habitat when that option is enabled.
The app must not be used to approve or execute a real EVA.

Moon speed (3 km/h), four-hour EVA duration, and 15-degree slope limit are
also assumptions. The configured 15 m roughness limit and two-cell safety
margin are planning settings, not validated lunar mobility limits. Moon dose
is not computed because no lunar radiation source is integrated.

Run the hazard and algorithm checks with:

```bash
python scripts/check_hazards.py
node scripts/check_hazards.js
node scripts/check_algorithms.js
python scripts/check_site_edge_cases.py
python scripts/check_moon.py --site site_01
node scripts/check_moon.js site_01
```

The endpoint edge-case script exercises hazard/margin snapping, disconnected
pockets, and over-limit plans for site3 and site4. Results for the four-site
hazard and algorithm checks are recorded in
[`docs/SITE_STRESS_TESTS.md`](docs/SITE_STRESS_TESTS.md).
The Moon source audit and per-site verification are in
[`docs/MOON_DATA_NOTES.md`](docs/MOON_DATA_NOTES.md) and
[`docs/MOON_TESTS.md`](docs/MOON_TESTS.md). Rebuilding Moon products requires
the git-ignored input rasters under `data/raw/moon/`; the committed processed
outputs are enough to run the map without those large source files.

## Project and data references

- [NASA Space Apps Challenge](https://www.spaceappschallenge.org/)
- [Interplanetary Survival Guide: Martian Map challenge](https://www.spaceappschallenge.org/2026/challenges/interplanetary-survival-guide-martian-map/)
- [NASA Mars Trek](https://trek.nasa.gov/mars/)
- [USGS Astrogeology interactive maps of Mars](https://astrogeology-usgs.hub.arcgis.com/pages/interactive-maps-mars)
- [NASA Science Curiosity route resource](https://science.nasa.gov/resource/curiositys-proposed-path-up-mount-sharp/)
- [NASA Worldview Earth observation viewer](https://worldview.earthdata.nasa.gov/)
- [NASA Mars 2020 raw images](https://mars.nasa.gov/mars2020/multimedia/raw-images/)

These sites provide challenge details and planetary mapping or imagery
references. They are not additional live data feeds in this app.

## Use of AI

AI tools, including GitHub Copilot, assisted with software development,
debugging, and documentation. The map does not use AI to generate or alter the
NASA imagery, elevation measurements, or route results. Routes are calculated
by the documented pathfinding algorithms; locations and EVA settings remain
explicitly labeled placeholders or assumptions.
