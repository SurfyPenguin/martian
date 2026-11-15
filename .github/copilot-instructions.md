# Martian Map

## Read first
Before any task, read docs/CHALLENGE.md (what judges want), docs/PLAN.md (our design),
and docs/STATUS.md (what is done and what is next). Update docs/STATUS.md at the end of every task.

Solo hackathon project (NASA Space Apps 2026, "Interplanetary Survival Guide: Martian Map").
Goal: a layered EVA planning map of a ~5x5 km area near Mount Sharp, Gale Crater, that
shows hazard/slope, imagery, minerals, and a radiation/weather panel, and computes a
low-risk walking route between 2-3 science targets.

## Stack
- Python 3.11+: rasterio, numpy, scikit-image, matplotlib (processing + route engine)
- Frontend: plain HTML/JS with Leaflet (no build step)

## Layout
- scripts/    Python data processing and route engine
- data/raw/   downloaded NASA data (gitignored, never commit)
- data/processed/  small outputs (slope raster, route.geojson)
- web/        Leaflet app (index.html, app.js, style.css)
- docs/PLAN.md  project plan; docs/reviews/  review notes

## Rules
- Never fabricate NASA data, file formats, or numbers. If a value is an assumption
  (max walkable slope, walking speed, radiation dose), put it in scripts/config.py
  with a comment and show it as an adjustable setting in the UI.
- Keep it simple: this must be demoable in under 24 hours.
- Small commits, Conventional Commit messages (feat:, fix:, docs:, chore:).
- Never commit files over 5 MB or anything in data/raw/.
- Run the code before claiming it works.