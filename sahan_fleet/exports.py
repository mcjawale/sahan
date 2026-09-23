import csv
import io
from datetime import datetime

from flask import (
    Blueprint,
    Response,
    render_template,
    request,
)

from .auth import login_required
from .db import get_db

bp = Blueprint("exports", __name__, url_prefix="/export")

TITLE = "MCJ Sahan Fleet Management System"

DATASETS = {
    "vehicles": {
        "title": "Vehicle Register",
        "sql": """SELECT v.plate_no, v.make, v.model, v.year, v.vehicle_type, v.fuel_type,
                         v.capacity, v.odometer, v.status, COALESCE(v.notes, '') AS notes
                  FROM vehicles v ORDER BY v.plate_no""",
        "headers": ["Plate No", "Make", "Model", "Year", "Type", "Fuel", "Capacity",
                    "Odometer (km)", "Status", "Notes"],
        "keys": ["plate_no", "make", "model", "year", "vehicle_type", "fuel_type",
                 "capacity", "odometer", "status", "notes"],
    },
    "drivers": {
        "title": "Driver Register",
        "sql": """SELECT employee_no, name, phone, email, license_no, license_expiry,
                         status, COALESCE(hired_at, '') AS hired_at
                  FROM drivers ORDER BY employee_no""",
        "headers": ["Employee No", "Name", "Phone", "Email", "License No",
                    "License Expiry", "Status", "Hired At"],
        "keys": ["employee_no", "name", "phone", "email", "license_no",
                 "license_expiry", "status", "hired_at"],
    },
    "routes": {
        "title": "Route Directory",
        "sql": "SELECT name, origin, destination, distance_km, estimated_hours FROM routes ORDER BY name",
        "headers": ["Route", "Origin", "Destination", "Distance (km)", "Est. Hours"],
        "keys": ["name", "origin", "destination", "distance_km", "estimated_hours"],
    },
    "trips": {
        "title": "Trip Report",
        "sql": """SELECT t.trip_no, COALESCE(r.name, '') AS route, COALESCE(r.origin, '') AS origin,
                         COALESCE(r.destination, '') AS destination,
                         COALESCE(v.plate_no, '') AS vehicle, COALESCE(d.name, '') AS driver,
                         COALESCE(t.departure_at, '') AS departure, COALESCE(t.arrival_at, '') AS arrival,
                         COALESCE(t.distance_km, 0) AS distance_km, t.status, t.revenue, t.cost,
                         (t.revenue - t.cost) AS profit, COALESCE(t.notes, '') AS notes
                  FROM trips t
                  LEFT JOIN routes r ON r.id = t.route_id
                  LEFT JOIN vehicles v ON v.id = t.vehicle_id
                  LEFT JOIN drivers d ON d.id = t.driver_id
                  ORDER BY t.departure_at DESC""",
        "headers": ["Trip No", "Route", "Origin", "Destination", "Vehicle", "Driver",
                    "Departure", "Arrival", "Distance (km)", "Status", "Revenue",
                    "Cost", "Profit", "Notes"],
        "keys": ["trip_no", "route", "origin", "destination", "vehicle", "driver",
                 "departure", "arrival", "distance_km", "status", "revenue", "cost",
                 "profit", "notes"],
    },
    "bookings": {
        "title": "Booking Manifest",
        "sql": """SELECT b.booking_no, b.passenger_name, COALESCE(b.phone, '') AS phone,
                         COALESCE(t.trip_no, '') AS trip_no, COALESCE(b.pickup, '') AS pickup,
                         COALESCE(b.dropoff, '') AS dropoff, b.seats, b.fare, b.status,
                         b.created_at
                  FROM bookings b
                  LEFT JOIN trips t ON t.id = b.trip_id
                  ORDER BY b.created_at DESC, b.id DESC""",
        "headers": ["Booking No", "Passenger", "Phone", "Trip No", "Pickup", "Dropoff",
                    "Seats", "Fare", "Status", "Created At"],
        "keys": ["booking_no", "passenger_name", "phone", "trip_no", "pickup",
                 "dropoff", "seats", "fare", "status", "created_at"],
    },
    "fuel": {
        "title": "Fuel Consumption Report",
        "sql": """SELECT f.ref_no, f.filled_at, v.plate_no, v.make || ' ' || v.model AS vehicle,
                         f.liters, f.cost, CASE WHEN f.liters > 0
                           THEN ROUND(f.cost / f.liters, 2) ELSE 0 END AS cost_per_liter,
                         COALESCE(f.station, '') AS station, COALESCE(f.odometer, '') AS odometer
                  FROM fuel_records f
                  JOIN vehicles v ON v.id = f.vehicle_id
                  ORDER BY f.filled_at DESC""",
        "headers": ["Ref No", "Date", "Plate No", "Vehicle", "Liters", "Cost",
                    "Cost/Liter", "Station", "Odometer"],
        "keys": ["ref_no", "filled_at", "plate_no", "vehicle", "liters", "cost",
                 "cost_per_liter", "station", "odometer"],
        "sum_keys": ["liters", "cost"],
    },
    "maintenance": {
        "title": "Maintenance Report",
        "sql": """SELECT v.plate_no, v.make || ' ' || v.model AS vehicle, m.maintenance_type,
                         COALESCE(m.description, '') AS description, m.started_at,
                         COALESCE(m.completed_at, '') AS completed_at, m.cost,
                         COALESCE(m.odometer, '') AS odometer, m.status,
                         COALESCE(m.next_due, '') AS next_due
                  FROM maintenance_records m
                  JOIN vehicles v ON v.id = m.vehicle_id
                  ORDER BY m.started_at DESC""",
        "headers": ["Plate No", "Vehicle", "Type", "Description", "Started", "Completed",
                    "Cost", "Odometer", "Status", "Next Due"],
        "keys": ["plate_no", "vehicle", "maintenance_type", "description", "started_at",
                 "completed_at", "cost", "odometer", "status", "next_due"],
        "sum_keys": ["cost"],
    },
    "financials": {
        "title": "Fleet Financial Summary",
        "sql": """SELECT
                    (SELECT COALESCE(SUM(revenue), 0) FROM trips) AS trip_revenue,
                    (SELECT COALESCE(SUM(cost), 0) FROM trips) AS trip_cost,
                    (SELECT COALESCE(SUM(cost), 0) FROM fuel_records) AS fuel_cost,
                    (SELECT COALESCE(SUM(cost), 0) FROM maintenance_records) AS maintenance_cost,
                    (SELECT COALESCE(SUM(fare), 0) FROM bookings WHERE status != 'cancelled') AS booking_fares,
                    (SELECT COUNT(*) FROM trips) AS total_trips,
                    (SELECT COUNT(*) FROM bookings WHERE status != 'cancelled') AS total_bookings,
                    (SELECT COALESCE(SUM(seats), 0) FROM bookings WHERE status != 'cancelled') AS total_seats""",
        "headers": ["Metric", "Value"],
        "keys": None,
    },
}


def _rows(key):
    ds = DATASETS[key]
    db = get_db()
    return [dict(r) for r in db.execute(ds["sql"]).fetchall()]


def _financial_rows(rows):
    r = rows[0]
    profit = r["trip_revenue"] - r["trip_cost"]
    return [
        {"Metric": "Trip Revenue", "Value": f"{r['trip_revenue']:,.2f}"},
        {"Metric": "Trip Operating Cost", "Value": f"{r['trip_cost']:,.2f}"},
        {"Metric": "Trip Profit", "Value": f"{profit:,.2f}"},
        {"Metric": "Fuel Spend (all time)", "Value": f"{r['fuel_cost']:,.2f}"},
        {"Metric": "Maintenance Spend (all time)", "Value": f"{r['maintenance_cost']:,.2f}"},
        {"Metric": "Booking Fares (all time)", "Value": f"{r['booking_fares']:,.2f}"},
        {"Metric": "Total Trips", "Value": r["total_trips"]},
        {"Metric": "Total Bookings", "Value": r["total_bookings"]},
        {"Metric": "Total Seats Booked", "Value": r["total_seats"]},
    ]


@bp.route("/")
@login_required
def reports():
    return render_template("reports.html", datasets=DATASETS)


def _table_data(key):
    ds = DATASETS[key]
    rows = _rows(key)
    if key == "financials":
        return ds["headers"], _financial_rows(rows)
    out = [{h: (r.get(k) if r.get(k) is not None else "") for h, k in zip(ds["headers"], ds["keys"])} for r in rows]
    if ds.get("sum_keys"):
        total = {h: "" for h in ds["headers"]}
        total[ds["headers"][0]] = "TOTAL"
        for sk in ds["sum_keys"]:
            idx = ds["keys"].index(sk)
            total[ds["headers"][idx]] = round(sum(r[sk] or 0 for r in rows), 2)
        out.append(total)
    return ds["headers"], out


@bp.route("/<key>/csv")
@login_required
def to_csv(key):
    if key not in DATASETS:
        return "Unknown dataset", 404
    headers, rows = _table_data(key)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    filename = f"sahan_fleet_{key}_{datetime.now():%Y%m%d}.csv"
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@bp.route("/<key>/pdf")
@login_required
def to_pdf(key):
    if key not in DATASETS:
        return "Unknown dataset", 404
    headers, rows = _table_data(key)
    title = DATASETS[key]["title"]

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    head = ParagraphStyle("H", parent=styles["Title"], fontSize=16, spaceAfter=2)
    sub = ParagraphStyle("S", parent=styles["Normal"], fontSize=9, textColor=colors.grey)
    cell = ParagraphStyle("C", parent=styles["Normal"], fontSize=7.5, leading=9)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=f"{title} - {TITLE}",
    )
    story = [
        Paragraph(TITLE, sub),
        Paragraph(title, head),
        Paragraph(f"Generated: {datetime.now():%Y-%m-%d %H:%M}", sub),
        Spacer(1, 8),
    ]

    data = [[Paragraph(str(h), cell) for h in headers]]
    for r in rows:
        data.append([Paragraph(str(r.get(h, "")), cell) for h in headers])

    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f4c5c")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        f"{len(rows)} record(s) | MCJ Sahan Fleet Management System | Page footer generated {datetime.now():%Y-%m-%d}",
        sub,
    ))
    doc.build(story)

    filename = f"sahan_fleet_{key}_{datetime.now():%Y%m%d}.pdf"
    return Response(
        buf.getvalue(),
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@bp.route("/<key>/print")
@login_required
def print_view(key):
    if key not in DATASETS:
        return "Unknown dataset", 404
    headers, rows = _table_data(key)
    return render_template(
        "print_table.html",
        title=DATASETS[key]["title"],
        headers=headers,
        rows=rows,
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
