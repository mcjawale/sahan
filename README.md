# MCJ Sahan Fleet Management System

A complete web-based transport / fleet management system for registering vehicles,
drivers and routes, scheduling trips, managing passenger bookings, tracking fuel
and maintenance costs, and producing printable reports in **CSV** and **PDF**.

## Features

- **Dashboard** – fleet utilisation, trip status, revenue vs cost, maintenance and licence-expiry alerts
- **Vehicles** – register buses, minibuses, vans, cars and trucks with capacity, odometer and status
- **Drivers** – licences, expiry tracking and duty status
- **Routes** – origin/destination, distance and estimated duration
- **Trips** – schedule trips, assign vehicle + driver, track revenue/cost, printable **trip sheet** with passenger manifest
- **Bookings** – passenger reservations with seats and fares, printable **receipt**
- **Fuel records** – litres, cost, cost-per-litre, station and odometer
- **Maintenance** – service, repair, inspection, tyres and insurance jobs with next-due dates
- **Reports & exports** – every register exports to **CSV**, **PDF** (landscape A4 with letterhead) and a **print view** (browser → Save as PDF)
- **Login** – session-based authentication (default `admin` / `admin123`)

## Quick start (local)

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000 and sign in with `admin` / `admin123`.

The SQLite database is created and seeded automatically on first run
(`instance/sahan_fleet.sqlite`). Useful commands:

```bash
flask --app app init-db     # initialise / seed
flask --app app reset-db    # drop everything and reseed
```

## Making it online (deployment)

The app is a standard Flask application (`wsgi.py` exposes `app`).

**Render / Railway / PythonAnywhere**

1. Push this folder to GitHub.
2. Create a new Web Service pointing at the repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn wsgi:app` (or `python app.py` for a quick test).
5. Set environment variables:
   - `SECRET_KEY` – a long random string (required for production)
   - `REQUIRE_LOGIN=1` – keep login enforced
   - `FLASK_DEBUG=0`

**Docker-less VPS**

```bash
pip install -r requirements.txt
SECRET_KEY="$(python -c 'import secrets;print(secrets.token_hex(32))')" gunicorn wsgi:app -b 0.0.0.0:8000
```

Put Nginx/Caddy in front for HTTPS. Change the admin password immediately
via **Account → Change Password** after first login.

## Printing & exporting

| Method | Where | Result |
|---|---|---|
| CSV | Any list page → **Export CSV**, or Reports page | Excel/Sheets-ready file |
| PDF | Any list page → **Export PDF**, or Reports page | Landscape A4 PDF with system letterhead |
| Print view | Any list page → **Print view** → browser Print | Clean printable page (Save as PDF) |
| Documents | Trip Sheet, Booking Receipt → **Print / Save PDF** | Signed operational documents |

## Project structure

```
app.py                 # dev entry point
wsgi.py                # production entry point (gunicorn wsgi:app)
requirements.txt
sahan_fleet/
  __init__.py          # app factory
  db.py                # schema, seeding, helpers
  auth.py              # login / logout / password
  dashboard.py         # KPI dashboard
  fleet.py             # vehicles, drivers, routes
  operations.py        # trips and bookings
  records.py           # fuel and maintenance
  exports.py           # CSV / PDF / print views
templates/             # Jinja2 pages
static/css/style.css   # styling + print styles
```

## Tech

Python 3 · Flask · SQLite · ReportLab (PDF)
