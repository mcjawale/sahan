from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from .auth import login_required
from .db import get_db, next_code

bp = Blueprint("operations", __name__, url_prefix="/ops")

TRIP_STATUS = ("scheduled", "in_transit", "completed", "cancelled")
BOOKING_STATUS = ("pending", "confirmed", "boarded", "completed", "cancelled")


def _q():
    return request.args.get("q", "").strip()


def _status():
    return request.args.get("status", "").strip()


def _filter(rows, fields, status_field="status"):
    q = _q().lower()
    st = _status()
    out = rows
    if st:
        out = [r for r in out if r[status_field] == st]
    if q:
        out = [r for r in out if any(q in str(r[f]).lower() for f in fields if f in r.keys())]
    return out


TRIP_SELECT = """SELECT t.*, r.name AS route_name, r.origin, r.destination,
                        v.plate_no, v.make AS vmake, v.model AS vmodel,
                        d.name AS driver_name, d.phone AS driver_phone,
                        (SELECT COALESCE(SUM(seats), 0) FROM bookings
                         WHERE trip_id = t.id AND status != 'cancelled') AS seats_booked
                 FROM trips t
                 LEFT JOIN routes r ON r.id = t.route_id
                 LEFT JOIN vehicles v ON v.id = t.vehicle_id
                 LEFT JOIN drivers d ON d.id = t.driver_id"""


# ---------- Trips ----------


@bp.route("/trips")
@login_required
def trips():
    db = get_db()
    rows = db.execute(TRIP_SELECT + " ORDER BY t.departure_at DESC").fetchall()
    return render_template(
        "ops/trips.html",
        rows=_filter(rows, ("trip_no", "route_name", "plate_no", "driver_name", "origin", "destination")),
        q=_q(),
        status=_status(),
        statuses=TRIP_STATUS,
    )


def _form_choices(db):
    return {
        "routes": db.execute("SELECT * FROM routes ORDER BY name").fetchall(),
        "vehicles": db.execute(
            "SELECT * FROM vehicles WHERE status != 'retired' ORDER BY plate_no"
        ).fetchall(),
        "drivers": db.execute(
            "SELECT * FROM drivers WHERE status != 'suspended' ORDER BY name"
        ).fetchall(),
    }


@bp.route("/trips/new", methods=("GET", "POST"))
@login_required
def trip_new():
    db = get_db()
    if request.method == "POST":
        form = request.form
        trip_no = next_code(db, "trips", "trip_no", "TRIP-")
        route = db.execute("SELECT * FROM routes WHERE id = ?", (form.get("route_id") or 0,)).fetchone()
        distance = form.get("distance_km") or (route["distance_km"] if route else 0)
        db.execute(
            """INSERT INTO trips
               (trip_no, route_id, vehicle_id, driver_id, departure_at, arrival_at,
                distance_km, status, revenue, cost, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                trip_no,
                form.get("route_id") or None,
                form.get("vehicle_id") or None,
                form.get("driver_id") or None,
                form.get("departure_at") or None,
                form.get("arrival_at") or None,
                distance,
                form.get("status", "scheduled"),
                form.get("revenue") or 0,
                form.get("cost") or 0,
                form.get("notes", "").strip(),
            ),
        )
        db.commit()
        flash(f"Trip {trip_no} created.", "ok")
        return redirect(url_for("operations.trips"))
    return render_template(
        "ops/trip_form.html", trip=None, statuses=TRIP_STATUS, **_form_choices(db)
    )


@bp.route("/trips/<int:tid>/edit", methods=("GET", "POST"))
@login_required
def trip_edit(tid):
    db = get_db()
    trip = db.execute("SELECT * FROM trips WHERE id = ?", (tid,)).fetchone()
    if trip is None:
        return redirect(url_for("operations.trips"))
    if request.method == "POST":
        form = request.form
        route = db.execute("SELECT * FROM routes WHERE id = ?", (form.get("route_id") or 0,)).fetchone()
        distance = form.get("distance_km") or (route["distance_km"] if route else 0)
        db.execute(
            """UPDATE trips SET route_id=?, vehicle_id=?, driver_id=?, departure_at=?,
               arrival_at=?, distance_km=?, status=?, revenue=?, cost=?, notes=? WHERE id=?""",
            (
                form.get("route_id") or None,
                form.get("vehicle_id") or None,
                form.get("driver_id") or None,
                form.get("departure_at") or None,
                form.get("arrival_at") or None,
                distance,
                form.get("status", "scheduled"),
                form.get("revenue") or 0,
                form.get("cost") or 0,
                form.get("notes", "").strip(),
                tid,
            ),
        )
        db.commit()
        flash("Trip updated.", "ok")
        return redirect(url_for("operations.trips"))
    return render_template(
        "ops/trip_form.html", trip=trip, statuses=TRIP_STATUS, **_form_choices(db)
    )


@bp.route("/trips/<int:tid>/delete", methods=("POST",))
@login_required
def trip_delete(tid):
    db = get_db()
    db.execute("DELETE FROM trips WHERE id = ?", (tid,))
    db.commit()
    flash("Trip deleted.", "ok")
    return redirect(url_for("operations.trips"))


@bp.route("/trips/<int:tid>/sheet")
@login_required
def trip_sheet(tid):
    db = get_db()
    trip = db.execute(TRIP_SELECT + " WHERE t.id = ?", (tid,)).fetchone()
    if trip is None:
        return redirect(url_for("operations.trips"))
    bookings = db.execute(
        "SELECT * FROM bookings WHERE trip_id = ? ORDER BY booking_no", (tid,)
    ).fetchall()
    return render_template("ops/trip_sheet.html", trip=trip, bookings=bookings)


# ---------- Bookings ----------


@bp.route("/bookings")
@login_required
def bookings():
    db = get_db()
    rows = db.execute(
        """SELECT b.*, t.trip_no, t.departure_at, r.name AS route_name,
                  r.origin, r.destination
           FROM bookings b
           LEFT JOIN trips t ON t.id = b.trip_id
           LEFT JOIN routes r ON r.id = t.route_id
           ORDER BY b.created_at DESC, b.id DESC"""
    ).fetchall()
    return render_template(
        "ops/bookings.html",
        rows=_filter(rows, ("booking_no", "passenger_name", "phone", "trip_no", "pickup", "dropoff")),
        q=_q(),
        status=_status(),
        statuses=BOOKING_STATUS,
    )


@bp.route("/bookings/new", methods=("GET", "POST"))
@login_required
def booking_new():
    db = get_db()
    if request.method == "POST":
        form = request.form
        booking_no = next_code(db, "bookings", "booking_no", "BK-")
        db.execute(
            """INSERT INTO bookings
               (booking_no, passenger_name, phone, trip_id, pickup, dropoff, seats, fare, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                booking_no,
                form.get("passenger_name", "").strip(),
                form.get("phone", "").strip(),
                form.get("trip_id") or None,
                form.get("pickup", "").strip(),
                form.get("dropoff", "").strip(),
                form.get("seats") or 1,
                form.get("fare") or 0,
                form.get("status", "pending"),
            ),
        )
        db.commit()
        flash(f"Booking {booking_no} created.", "ok")
        return redirect(url_for("operations.bookings"))
    trips = db.execute(
        """SELECT t.id, t.trip_no, t.departure_at, t.status,
                  COALESCE(r.name, t.trip_no) AS label
           FROM trips t LEFT JOIN routes r ON r.id = t.route_id
           WHERE t.status IN ('scheduled', 'in_transit')
           ORDER BY t.departure_at"""
    ).fetchall()
    return render_template("ops/booking_form.html", booking=None, trips=trips, statuses=BOOKING_STATUS)


@bp.route("/bookings/<int:bid>/edit", methods=("GET", "POST"))
@login_required
def booking_edit(bid):
    db = get_db()
    booking = db.execute("SELECT * FROM bookings WHERE id = ?", (bid,)).fetchone()
    if booking is None:
        return redirect(url_for("operations.bookings"))
    if request.method == "POST":
        form = request.form
        db.execute(
            """UPDATE bookings SET passenger_name=?, phone=?, trip_id=?, pickup=?, dropoff=?,
               seats=?, fare=?, status=? WHERE id=?""",
            (
                form.get("passenger_name", "").strip(),
                form.get("phone", "").strip(),
                form.get("trip_id") or None,
                form.get("pickup", "").strip(),
                form.get("dropoff", "").strip(),
                form.get("seats") or 1,
                form.get("fare") or 0,
                form.get("status", "pending"),
                bid,
            ),
        )
        db.commit()
        flash("Booking updated.", "ok")
        return redirect(url_for("operations.bookings"))
    trips = db.execute(
        """SELECT t.id, t.trip_no, t.departure_at, t.status,
                  COALESCE(r.name, t.trip_no) AS label
           FROM trips t LEFT JOIN routes r ON r.id = t.route_id
           ORDER BY t.departure_at"""
    ).fetchall()
    return render_template(
        "ops/booking_form.html", booking=booking, trips=trips, statuses=BOOKING_STATUS
    )


@bp.route("/bookings/<int:bid>/delete", methods=("POST",))
@login_required
def booking_delete(bid):
    db = get_db()
    db.execute("DELETE FROM bookings WHERE id = ?", (bid,))
    db.commit()
    flash("Booking deleted.", "ok")
    return redirect(url_for("operations.bookings"))


@bp.route("/bookings/<int:bid>/receipt")
@login_required
def booking_receipt(bid):
    db = get_db()
    booking = db.execute(
        """SELECT b.*, t.trip_no, t.departure_at, r.name AS route_name,
                  r.origin, r.destination, v.plate_no, d.name AS driver_name
           FROM bookings b
           LEFT JOIN trips t ON t.id = b.trip_id
           LEFT JOIN routes r ON r.id = t.route_id
           LEFT JOIN vehicles v ON v.id = t.vehicle_id
           LEFT JOIN drivers d ON d.id = t.driver_id
           WHERE b.id = ?""",
        (bid,),
    ).fetchone()
    if booking is None:
        return redirect(url_for("operations.bookings"))
    return render_template("ops/booking_receipt.html", b=booking)
