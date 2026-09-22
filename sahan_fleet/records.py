from flask import Blueprint, flash, redirect, render_template, request, url_for

from .auth import login_required
from .db import get_db, next_code

bp = Blueprint("records", __name__, url_prefix="/records")

MAINT_TYPES = ("service", "repair", "inspection", "tyres", "insurance")
MAINT_STATUS = ("scheduled", "in_progress", "completed")


def _q():
    return request.args.get("q", "").strip()


def _search(rows, fields):
    q = _q().lower()
    if not q:
        return rows
    return [r for r in rows if any(q in str(r[f]).lower() for f in fields if f in r.keys())]


# ---------- Fuel ----------


@bp.route("/fuel")
@login_required
def fuel():
    db = get_db()
    rows = db.execute(
        """SELECT f.*, v.plate_no, v.make, v.model
           FROM fuel_records f
           JOIN vehicles v ON v.id = f.vehicle_id
           ORDER BY f.filled_at DESC, f.id DESC"""
    ).fetchall()
    total_cost = sum(r["cost"] for r in rows)
    total_liters = sum(r["liters"] for r in rows)
    return render_template(
        "records/fuel.html",
        rows=_search(rows, ("ref_no", "plate_no", "make", "model", "station")),
        q=_q(),
        total_cost=total_cost,
        total_liters=total_liters,
    )


@bp.route("/fuel/new", methods=("GET", "POST"))
@login_required
def fuel_new():
    db = get_db()
    if request.method == "POST":
        form = request.form
        ref = form.get("ref_no", "").strip().upper() or next_code(db, "fuel_records", "ref_no", "FUEL-")
        try:
            db.execute(
                """INSERT INTO fuel_records
                   (vehicle_id, ref_no, filled_at, liters, cost, station, odometer)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    form.get("vehicle_id"),
                    ref,
                    form.get("filled_at"),
                    form.get("liters") or 0,
                    form.get("cost") or 0,
                    form.get("station", "").strip(),
                    form.get("odometer") or None,
                ),
            )
            db.commit()
            flash("Fuel record added.", "ok")
            return redirect(url_for("records.fuel"))
        except Exception:
            flash("Could not save fuel record.", "error")
    vehicles = db.execute("SELECT * FROM vehicles ORDER BY plate_no").fetchall()
    return render_template("records/fuel_form.html", record=None, vehicles=vehicles)


@bp.route("/fuel/<int:fid>/edit", methods=("GET", "POST"))
@login_required
def fuel_edit(fid):
    db = get_db()
    record = db.execute("SELECT * FROM fuel_records WHERE id = ?", (fid,)).fetchone()
    if record is None:
        return redirect(url_for("records.fuel"))
    if request.method == "POST":
        form = request.form
        db.execute(
            """UPDATE fuel_records SET vehicle_id=?, ref_no=?, filled_at=?, liters=?,
               cost=?, station=?, odometer=? WHERE id=?""",
            (
                form.get("vehicle_id"),
                form.get("ref_no", "").strip().upper(),
                form.get("filled_at"),
                form.get("liters") or 0,
                form.get("cost") or 0,
                form.get("station", "").strip(),
                form.get("odometer") or None,
                fid,
            ),
        )
        db.commit()
        flash("Fuel record updated.", "ok")
        return redirect(url_for("records.fuel"))
    vehicles = db.execute("SELECT * FROM vehicles ORDER BY plate_no").fetchall()
    return render_template("records/fuel_form.html", record=record, vehicles=vehicles)


@bp.route("/fuel/<int:fid>/delete", methods=("POST",))
@login_required
def fuel_delete(fid):
    db = get_db()
    db.execute("DELETE FROM fuel_records WHERE id = ?", (fid,))
    db.commit()
    flash("Fuel record deleted.", "ok")
    return redirect(url_for("records.fuel"))


# ---------- Maintenance ----------


@bp.route("/maintenance")
@login_required
def maintenance():
    db = get_db()
    rows = db.execute(
        """SELECT m.*, v.plate_no, v.make, v.model
           FROM maintenance_records m
           JOIN vehicles v ON v.id = m.vehicle_id
           ORDER BY m.started_at DESC, m.id DESC"""
    ).fetchall()
    total_cost = sum(r["cost"] for r in rows)
    open_count = sum(1 for r in rows if r["status"] != "completed")
    return render_template(
        "records/maintenance.html",
        rows=_search(rows, ("plate_no", "make", "model", "description", "maintenance_type", "status")),
        q=_q(),
        total_cost=total_cost,
        open_count=open_count,
        maint_types=MAINT_TYPES,
        maint_status=MAINT_STATUS,
    )


@bp.route("/maintenance/new", methods=("GET", "POST"))
@login_required
def maintenance_new():
    db = get_db()
    if request.method == "POST":
        form = request.form
        db.execute(
            """INSERT INTO maintenance_records
               (vehicle_id, maintenance_type, description, started_at, completed_at,
                cost, odometer, status, next_due)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                form.get("vehicle_id"),
                form.get("maintenance_type", "service"),
                form.get("description", "").strip(),
                form.get("started_at"),
                form.get("completed_at") or None,
                form.get("cost") or 0,
                form.get("odometer") or None,
                form.get("status", "scheduled"),
                form.get("next_due") or None,
            ),
        )
        if form.get("status") == "in_progress" and form.get("vehicle_id"):
            db.execute(
                "UPDATE vehicles SET status = 'maintenance' WHERE id = ?",
                (form.get("vehicle_id"),),
            )
        db.commit()
        flash("Maintenance record added.", "ok")
        return redirect(url_for("records.maintenance"))
    vehicles = db.execute("SELECT * FROM vehicles ORDER BY plate_no").fetchall()
    return render_template(
        "records/maintenance_form.html",
        record=None,
        vehicles=vehicles,
        maint_types=MAINT_TYPES,
        maint_status=MAINT_STATUS,
    )


@bp.route("/maintenance/<int:mid>/edit", methods=("GET", "POST"))
@login_required
def maintenance_edit(mid):
    db = get_db()
    record = db.execute("SELECT * FROM maintenance_records WHERE id = ?", (mid,)).fetchone()
    if record is None:
        return redirect(url_for("records.maintenance"))
    if request.method == "POST":
        form = request.form
        db.execute(
            """UPDATE maintenance_records SET vehicle_id=?, maintenance_type=?, description=?,
               started_at=?, completed_at=?, cost=?, odometer=?, status=?, next_due=? WHERE id=?""",
            (
                form.get("vehicle_id"),
                form.get("maintenance_type", "service"),
                form.get("description", "").strip(),
                form.get("started_at"),
                form.get("completed_at") or None,
                form.get("cost") or 0,
                form.get("odometer") or None,
                form.get("status", "scheduled"),
                form.get("next_due") or None,
                mid,
            ),
        )
        if form.get("status") == "completed" and form.get("vehicle_id"):
            db.execute(
                "UPDATE vehicles SET status = 'available' WHERE id = ? AND status = 'maintenance'",
                (form.get("vehicle_id"),),
            )
        db.commit()
        flash("Maintenance record updated.", "ok")
        return redirect(url_for("records.maintenance"))
    vehicles = db.execute("SELECT * FROM vehicles ORDER BY plate_no").fetchall()
    return render_template(
        "records/maintenance_form.html",
        record=record,
        vehicles=vehicles,
        maint_types=MAINT_TYPES,
        maint_status=MAINT_STATUS,
    )


@bp.route("/maintenance/<int:mid>/delete", methods=("POST",))
@login_required
def maintenance_delete(mid):
    db = get_db()
    db.execute("DELETE FROM maintenance_records WHERE id = ?", (mid,))
    db.commit()
    flash("Maintenance record deleted.", "ok")
    return redirect(url_for("records.maintenance"))
