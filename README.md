# CivicLens

**Report it. Rank it. Track it.** CivicLens helps residents report local problems and gives municipal teams a transparent way to prioritise, route, and resolve them.

## Product idea

The important product distinction is between a **report** (one resident's submission) and an **issue** (the underlying real-world problem). Nearby reports for the same category can be grouped into one issue; its priority reflects community activity as well as impact and urgency. Residents can follow the issue through assignment, work in progress, and resolution.

### Proposed priority model

`priority = trust × (0.35 × severity + 0.25 × location sensitivity + 0.20 × report frequency + 0.20 × age)`

Each factor is normalised to 0–100. Trust is a confidence multiplier derived from verification. The score and its component values should be saved with the issue so the UI can show **Why this score?** and the city can audit why a score changed. Re-score open issues as they age. Keep weights configurable and calibrate them with municipal staff; the initial weights are a demo starting point, not a validated policy.

## Stack analysis

The supplied plan recommends a thin, low-risk stack for a two-day prototype:

- **FastAPI + Jinja2** serves the resident and officer pages and owns all data access.
- **HTML, CSS, and vanilla JavaScript** keep the first UI quick to build and easy to run without a frontend build pipeline.
- **SQLite + SQLAlchemy** fit an offline demo and keep a later move to PostgreSQL behind the database URL. Add PostGIS when real geospatial querying is needed.
- **Leaflet + OpenStreetMap** are a natural map choice once a real tile source and geocoding approach are configured. The current map is a dependency-free illustrative ward map.
- **Photo storage** can start on local disk for a demo, then move to object storage. Keep photo metadata separate from public issue data.
- A background queue is appropriate at city scale, but is not needed for the first working slice. Start with synchronous processing; add a worker for image checks, deduplication, notifications, and periodic rescoring when load requires it.

The plan's risk controls matter: keep database calls on the server, do not expose reporter names or exact home coordinates publicly, validate uploads, rate-limit reporting/auth flows, and distinguish simulated OTP/verification from production identity checks. A score should help staff triage, with a visible explanation and human review path.

## Current UI slice

The interface includes a resident public tracker, priority-ranked issue list with search and status filters, an illustrated map, an issue detail panel with score factors and lifecycle, an issue submission form, and an officer queue with status updates and CSV export. The data is in-memory demo data; report submissions and status changes reset when the server page reloads. GPS, OTP, photo upload storage, deduplication, notifications, and database persistence are not connected yet.

## Run locally

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. The current UI is self-contained apart from the optional Google Fonts request; no map or JavaScript CDN is required.

### Quest 1 foundation

The application now has a small package structure under `app/`, SQLAlchemy wired to a local SQLite database by default, and a liveness endpoint:

```text
app/
├── config.py
├── database.py
├── main.py
└── routes/
    └── health.py
```

Check the running service at http://127.0.0.1:8000/health. To use another database later, set `CIVICLENS_DATABASE_URL` before starting the server.

### Quest 2 database

The database foundation now creates these SQLite tables on application startup:

- `users`: citizen/officer identity and trust metadata.
- `reports`: individual citizen submissions, including coordinates and optional photos.
- `issues`: deduplicated real-world problems with priority and lifecycle fields.
- `status_log`: an audit trail for every issue status transition.

The `Report` to `Issue` relationship is intentionally nullable so a new report can be stored before the deduplication service attaches it to an existing issue. The same SQLAlchemy models can use PostgreSQL later by changing `CIVICLENS_DATABASE_URL`.

## Suggested next build steps

1. Add SQLAlchemy models for users, reports, issues, and status history.
2. Move the demo issues into a seed script and expose read endpoints for the tracker and queue.
3. Persist report submissions and status transitions, then add deterministic category-and-distance deduplication.
4. Add server-side validation, upload limits, a simulated OTP flow, and privacy-safe public serializers.
5. Replace the illustrative map with Leaflet and a configured tile provider; add geospatial storage when moving to PostgreSQL/PostGIS.
