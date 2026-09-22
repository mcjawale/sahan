import math
from datetime import date, timedelta

from flask import Blueprint, current_app, g, render_template

from .auth import login_required
from .db import get_db

bp = Blueprint("dashboard", __name__)

DONUT_ORDER = ("scheduled", "in_transit", "completed", "cancelled")
DONUT_COLORS = {
    "scheduled": "#e36414",
    "in_transit": "#3b82f6",
    "completed": "#16a34a",
    "cancelled": "#ef4444",
}


@bp.before_app_request
def load_user():
    from flask import session

    g.user_id = session.get("user_id")
    g.user_name = session.get("user_name")
    if g.user_id is None and current_app.config.get("REQUIRE_LOGIN") is False:
        db = get_db()
        row = db.execute("SELECT id FROM users LIMIT 1").fetchone()
        if row:
            g.user_id = row["id"]
            g.user_name = "Guest Operator"


@bp.route("/")
@login_required
def index():
    db = get_db()

    def one(sql, params=()):
        return db.execute(sql, params).fetchone()[0]

    stats = {
        "vehicles_total": one("SELECT COUNT(*) FROM vehicles"),
        "vehicles_available": one(
            "SELECT COUNT(*) FROM vehicles WHERE status = 'available'"
        ),
        "vehicles_maintenance": one(
            "SELECT COUNT(*) FROM vehicles WHERE status = 'maintenance'"
        ),
        "drivers_available": one(
            "SELECT COUNT(*) FROM drivers WHERE status = 'available'"
        ),
        "trips_active": one(
            "SELECT COUNT(*) FROM trips WHERE status IN ('scheduled', 'in_transit')"
        ),
        "trips_completed": one("SELECT COUNT(*) FROM trips WHERE status = 'completed'"),
        "bookings_pending": one(
            "SELECT COUNT(*) FROM bookings WHERE status = 'pending'"
        ),
        "bookings_total": one("SELECT COUNT(*) FROM bookings"),
        "revenue": one("SELECT COALESCE(SUM(revenue), 0) FROM trips"),
        "cost": one("SELECT COALESCE(SUM(cost), 0) FROM trips"),
        "fuel_spend": one(
            "SELECT COALESCE(SUM(cost), 0) FROM fuel_records "
            "WHERE filled_at >= date('now', 'start of month')"
        ),
        "maintenance_due": one(
            "SELECT COUNT(*) FROM maintenance_records "
            "WHERE status != 'completed' OR (next_due IS NOT NULL AND next_due <= date('now', '+30 day'))"
        ),
        "passengers": one("SELECT COALESCE(SUM(seats), 0) FROM bookings WHERE status != 'cancelled'"),
    }
    stats["profit"] = stats["revenue"] - stats["cost"]

    recent_trips = db.execute(
        """SELECT t.*, r.name AS route_name, r.origin, r.destination,
                  v.plate_no, v.model, d.name AS driver_name,
                  (SELECT COALESCE(SUM(seats), 0) FROM bookings
                   WHERE trip_id = t.id AND status != 'cancelled') AS seats_booked
           FROM trips t
           LEFT JOIN routes r ON r.id = t.route_id
           LEFT JOIN vehicles v ON v.id = t.vehicle_id
           LEFT JOIN drivers d ON d.id = t.driver_id
           ORDER BY t.departure_at DESC LIMIT 8"""
    ).fetchall()

    status_rows = db.execute(
        "SELECT status, COUNT(*) AS n FROM trips GROUP BY status"
    ).fetchall()
    trip_status = {r["status"]: r["n"] for r in status_rows}

    vehicle_rows = db.execute(
        "SELECT status, COUNT(*) AS n FROM vehicles GROUP BY status"
    ).fetchall()
    vehicle_status = {r["status"]: r["n"] for r in vehicle_rows}

    upcoming = db.execute(
        """SELECT t.id, t.trip_no, t.departure_at, t.status, r.name AS route_name,
                  v.plate_no, d.name AS driver_name,
                  (SELECT COALESCE(SUM(seats), 0) FROM bookings
                   WHERE trip_id = t.id AND status IN ('confirmed', 'boarded', 'pending')) AS seats_booked
           FROM trips t
           LEFT JOIN routes r ON r.id = t.route_id
           LEFT JOIN vehicles v ON v.id = t.vehicle_id
           LEFT JOIN drivers d ON d.id = t.driver_id
           WHERE t.status = 'scheduled'
           ORDER BY t.departure_at ASC LIMIT 5"""
    ).fetchall()

    alerts = db.execute(
        """SELECT v.plate_no, v.make, v.model, m.description, m.next_due, m.status
           FROM maintenance_records m
           JOIN vehicles v ON v.id = m.vehicle_id
           WHERE m.status IN ('scheduled', 'in_progress')
              OR (m.next_due IS NOT NULL AND m.next_due <= date('now', '+30 day'))
           ORDER BY COALESCE(m.next_due, m.started_at) ASC LIMIT 5"""
    ).fetchall()

    license_alerts = db.execute(
        """SELECT name, license_no, license_expiry FROM drivers
           WHERE license_expiry IS NOT NULL AND license_expiry <= date('now', '+60 day')
           ORDER BY license_expiry ASC LIMIT 5"""
    ).fetchall()

    circ = 2 * math.pi * 15.9155
    trip_total = max(sum(trip_status.values()), 1)
    donut = []
    acc = 0.0
    for st in DONUT_ORDER:
        n = trip_status.get(st, 0)
        frac = n / trip_total
        donut.append(
            {
                "label": st.replace("_", " "),
                "n": n,
                "color": DONUT_COLORS[st],
                "dash": f"{frac * circ:.2f} {circ:.2f}",
                "offset": f"{-acc * circ:.2f}",
            }
        )
        acc += frac

    days = [(date.today() - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    marks = ",".join("?" * len(days))
    series = db.execute(
        f"""SELECT substr(departure_at, 1, 10) AS d,
                   COALESCE(SUM(revenue), 0) AS rev,
                   COALESCE(SUM(cost), 0) AS cost
            FROM trips WHERE substr(departure_at, 1, 10) IN ({marks})
            GROUP BY substr(departure_at, 1, 10)""",
        days,
    ).fetchall()
    by_day = {r["d"]: r for r in series}
    chart = [
        {
            "label": d[5:],
            "rev": round(by_day[d]["rev"]) if d in by_day else 0,
            "cost": round(by_day[d]["cost"]) if d in by_day else 0,
            "day": d[8:],
        }
        for d in days
    ]
    chart_max = max(max(c["rev"], c["cost"]) for c in chart) or 1

    fuel_rows = db.execute(
        """SELECT v.plate_no, COALESCE(SUM(f.cost), 0) AS cost
           FROM fuel_records f JOIN vehicles v ON v.id = f.vehicle_id
           WHERE f.filled_at >= date('now', '-30 day')
           GROUP BY v.id ORDER BY cost DESC LIMIT 5"""
    ).fetchall()
    fuel_max = max((r["cost"] for r in fuel_rows), default=0) or 1
    fuel_bars = [
        {"plate": r["plate_no"], "cost": round(r["cost"]), "pct": r["cost"] / fuel_max * 100}
        for r in fuel_rows
    ]

    fleet_rows = db.execute(
        """SELECT vehicle_type, COUNT(*) AS n FROM vehicles GROUP BY vehicle_type ORDER BY n DESC"""
    ).fetchall()
    fleet_share = {r["vehicle_type"]: r["n"] for r in fleet_rows}

    return render_template(
        "dashboard.html",
        stats=stats,
        recent_trips=recent_trips,
        trip_status=trip_status,
        donut=donut,
        trip_total=trip_total,
        vehicle_status=vehicle_status,
        chart=chart,
        chart_max=chart_max,
        fuel_bars=fuel_bars,
        fleet_share=fleet_share,
        upcoming=upcoming,
        alerts=alerts,
        license_alerts=license_alerts,
    )
