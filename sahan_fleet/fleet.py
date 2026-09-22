from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from .auth import login_required
from .db import get_db

bp = Blueprint("fleet", __name__, url_prefix="/fleet")

VEHICLE_TYPES = ("bus", "minibus", "van", "car", "truck", "motorcycle")
VEHICLE_STATUS = ("available", "in_service", "maintenance", "retired")
DRIVER_STATUS = ("available", "on_trip", "off_duty", "suspended")


def _q():
    return request.args.get("q", "").strip()


def _search(rows, fields):
    q = _q().lower()
    if not q:
        return rows
    return [r for r in rows if any(q in str(r[f]).lower() for f in fields)]


# ---------- Vehicles ----------


@bp.route("/vehicles")
@login_required
def vehicles():
    db = get_db()
    rows = db.execute("SELECT * FROM vehicles ORDER BY plate_no").fetchall()
    return render_template(
        "fleet/vehicles.html", rows=_search(rows, ("plate_no", "make", "model", "status", "vehicle_type")), q=_q()
    )


@bp.route("/vehicles/new", methods=("GET", "POST"))
@login_required
def vehicle_new():
    if request.method == "POST":
        db = get_db()
        form = request.form
        try:
            db.execute(
                """INSERT INTO vehicles
                   (plate_no, make, model, year, vehicle_type, fuel_type, capacity,
                    odometer, status, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    form.get("plate_no", "").strip().upper(),
                    form.get("make", "").strip(),
                    form.get("model", "").strip(),
                    form.get("year") or None,
                    form.get("vehicle_type", "bus"),
                    form.get("fuel_type", "diesel"),
                    form.get("capacity") or 0,
                    form.get("odometer") or 0,
                    form.get("status", "available"),
                    form.get("notes", "").strip(),
                ),
            )
            db.commit()
            flash("Vehicle added.", "ok")
            return redirect(url_for("fleet.vehicles"))
        except Exception:
            flash("Could not save vehicle (duplicate plate number?).", "error")
    return render_template(
        "fleet/vehicle_form.html",
        vehicle=None,
        vehicle_types=VEHICLE_TYPES,
        vehicle_status=VEHICLE_STATUS,
    )


@bp.route("/vehicles/<int:vid>/edit", methods=("GET", "POST"))
@login_required
def vehicle_edit(vid):
    db = get_db()
    vehicle = db.execute("SELECT * FROM vehicles WHERE id = ?", (vid,)).fetchone()
    if vehicle is None:
        return redirect(url_for("fleet.vehicles"))
    if request.method == "POST":
        form = request.form
        try:
            db.execute(
                """UPDATE vehicles SET plate_no=?, make=?, model=?, year=?, vehicle_type=?,
                   fuel_type=?, capacity=?, odometer=?, status=?, notes=? WHERE id=?""",
                (
                    form.get("plate_no", "").strip().upper(),
                    form.get("make", "").strip(),
                    form.get("model", "").strip(),
                    form.get("year") or None,
                    form.get("vehicle_type", "bus"),
                    form.get("fuel_type", "diesel"),
                    form.get("capacity") or 0,
                    form.get("odometer") or 0,
                    form.get("status", "available"),
                    form.get("notes", "").strip(),
                    vid,
                ),
            )
            db.commit()
            flash("Vehicle updated.", "ok")
            return redirect(url_for("fleet.vehicles"))
        except Exception:
            flash("Could not update vehicle (duplicate plate number?).", "error")
    return render_template(
        "fleet/vehicle_form.html",
        vehicle=vehicle,
        vehicle_types=VEHICLE_TYPES,
        vehicle_status=VEHICLE_STATUS,
    )


@bp.route("/vehicles/<int:vid>/delete", methods=("POST",))
@login_required
def vehicle_delete(vid):
    db = get_db()
    used = db.execute(
        "SELECT COUNT(*) FROM trips WHERE vehicle_id = ? AND status != 'cancelled'", (vid,)
    ).fetchone()[0]
    if used:
        flash("Vehicle has active trip history and cannot be deleted.", "error")
    else:
        db.execute("DELETE FROM vehicles WHERE id = ?", (vid,))
        db.commit()
        flash("Vehicle deleted.", "ok")
    return redirect(url_for("fleet.vehicles"))


# ---------- Drivers ----------


@bp.route("/drivers")
@login_required
def drivers():
    db = get_db()
    rows = db.execute("SELECT * FROM drivers ORDER BY employee_no").fetchall()
    return render_template(
        "fleet/drivers.html", rows=_search(rows, ("employee_no", "name", "phone", "status", "license_no")), q=_q()
    )


@bp.route("/drivers/new", methods=("GET", "POST"))
@login_required
def driver_new():
    if request.method == "POST":
        db = get_db()
        form = request.form
        emp = form.get("employee_no", "").strip().upper() or None
        if emp is None:
            from .db import next_code

            emp = next_code(db, "drivers", "employee_no", "DRV-")
        try:
            db.execute(
                """INSERT INTO drivers
                   (employee_no, name, phone, email, license_no, license_expiry, status, hired_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    emp,
                    form.get("name", "").strip(),
                    form.get("phone", "").strip(),
                    form.get("email", "").strip(),
                    form.get("license_no", "").strip(),
                    form.get("license_expiry") or None,
                    form.get("status", "available"),
                    form.get("hired_at") or None,
                ),
            )
            db.commit()
            flash("Driver added.", "ok")
            return redirect(url_for("fleet.drivers"))
        except Exception:
            flash("Could not save driver (duplicate employee number?).", "error")
    return render_template(
        "fleet/driver_form.html", driver=None, driver_status=DRIVER_STATUS
    )


@bp.route("/drivers/<int:did>/edit", methods=("GET", "POST"))
@login_required
def driver_edit(did):
    db = get_db()
    driver = db.execute("SELECT * FROM drivers WHERE id = ?", (did,)).fetchone()
    if driver is None:
        return redirect(url_for("fleet.drivers"))
    if request.method == "POST":
        form = request.form
        try:
            db.execute(
                """UPDATE drivers SET employee_no=?, name=?, phone=?, email=?, license_no=?,
                   license_expiry=?, status=?, hired_at=? WHERE id=?""",
                (
                    form.get("employee_no", "").strip().upper(),
                    form.get("name", "").strip(),
                    form.get("phone", "").strip(),
                    form.get("email", "").strip(),
                    form.get("license_no", "").strip(),
                    form.get("license_expiry") or None,
                    form.get("status", "available"),
                    form.get("hired_at") or None,
                    did,
                ),
            )
            db.commit()
            flash("Driver updated.", "ok")
            return redirect(url_for("fleet.drivers"))
        except Exception:
            flash("Could not update driver (duplicate employee number?).", "error")
    return render_template(
        "fleet/driver_form.html", driver=driver, driver_status=DRIVER_STATUS
    )


@bp.route("/drivers/<int:did>/delete", methods=("POST",))
@login_required
def driver_delete(did):
    db = get_db()
    used = db.execute(
        "SELECT COUNT(*) FROM trips WHERE driver_id = ? AND status != 'cancelled'", (did,)
    ).fetchone()[0]
    if used:
        flash("Driver has active trip history and cannot be deleted.", "error")
    else:
        db.execute("DELETE FROM drivers WHERE id = ?", (did,))
        db.commit()
        flash("Driver deleted.", "ok")
    return redirect(url_for("fleet.drivers"))


# ---------- Routes ----------


@bp.route("/routes")
@login_required
def routes():
    db = get_db()
    rows = db.execute("SELECT * FROM routes ORDER BY name").fetchall()
    return render_template(
        "fleet/routes.html", rows=_search(rows, ("name", "origin", "destination")), q=_q()
    )


@bp.route("/routes/new", methods=("GET", "POST"))
@login_required
def route_new():
    if request.method == "POST":
        db = get_db()
        form = request.form
        db.execute(
            """INSERT INTO routes (name, origin, destination, distance_km, estimated_hours)
               VALUES (?, ?, ?, ?, ?)""",
            (
                form.get("name", "").strip(),
                form.get("origin", "").strip(),
                form.get("destination", "").strip(),
                form.get("distance_km") or 0,
                form.get("estimated_hours") or 0,
            ),
        )
        db.commit()
        flash("Route added.", "ok")
        return redirect(url_for("fleet.routes"))
    return render_template("fleet/route_form.html", route=None)


@bp.route("/routes/<int:rid>/edit", methods=("GET", "POST"))
@login_required
def route_edit(rid):
    db = get_db()
    route = db.execute("SELECT * FROM routes WHERE id = ?", (rid,)).fetchone()
    if route is None:
        return redirect(url_for("fleet.routes"))
    if request.method == "POST":
        form = request.form
        db.execute(
            """UPDATE routes SET name=?, origin=?, destination=?, distance_km=?, estimated_hours=?
               WHERE id=?""",
            (
                form.get("name", "").strip(),
                form.get("origin", "").strip(),
                form.get("destination", "").strip(),
                form.get("distance_km") or 0,
                form.get("estimated_hours") or 0,
                rid,
            ),
        )
        db.commit()
        flash("Route updated.", "ok")
        return redirect(url_for("fleet.routes"))
    return render_template("fleet/route_form.html", route=route)


@bp.route("/routes/<int:rid>/delete", methods=("POST",))
@login_required
def route_delete(rid):
    db = get_db()
    db.execute("DELETE FROM routes WHERE id = ?", (rid,))
    db.commit()
    flash("Route deleted.", "ok")
    return redirect(url_for("fleet.routes"))
