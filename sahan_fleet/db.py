import sqlite3

import click
from flask import current_app, g

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'operator'
);

CREATE TABLE IF NOT EXISTS drivers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_no TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    license_no TEXT,
    license_expiry DATE,
    status TEXT NOT NULL DEFAULT 'available'
        CHECK (status IN ('available', 'on_trip', 'off_duty', 'suspended')),
    hired_at DATE
);

CREATE TABLE IF NOT EXISTS vehicles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plate_no TEXT UNIQUE NOT NULL,
    make TEXT NOT NULL,
    model TEXT NOT NULL,
    year INTEGER,
    vehicle_type TEXT NOT NULL DEFAULT 'bus'
        CHECK (vehicle_type IN ('bus', 'minibus', 'van', 'car', 'truck', 'motorcycle')),
    fuel_type TEXT NOT NULL DEFAULT 'diesel',
    capacity INTEGER NOT NULL DEFAULT 0,
    odometer REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'available'
        CHECK (status IN ('available', 'in_service', 'maintenance', 'retired')),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    distance_km REAL NOT NULL DEFAULT 0,
    estimated_hours REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS trips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_no TEXT UNIQUE NOT NULL,
    route_id INTEGER REFERENCES routes(id) ON DELETE SET NULL,
    vehicle_id INTEGER REFERENCES vehicles(id) ON DELETE SET NULL,
    driver_id INTEGER REFERENCES drivers(id) ON DELETE SET NULL,
    departure_at TEXT,
    arrival_at TEXT,
    distance_km REAL,
    status TEXT NOT NULL DEFAULT 'scheduled'
        CHECK (status IN ('scheduled', 'in_transit', 'completed', 'cancelled')),
    revenue REAL NOT NULL DEFAULT 0,
    cost REAL NOT NULL DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_no TEXT UNIQUE NOT NULL,
    passenger_name TEXT NOT NULL,
    phone TEXT,
    trip_id INTEGER REFERENCES trips(id) ON DELETE SET NULL,
    pickup TEXT,
    dropoff TEXT,
    seats INTEGER NOT NULL DEFAULT 1,
    fare REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'confirmed', 'boarded', 'completed', 'cancelled')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS fuel_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
    ref_no TEXT,
    filled_at DATE NOT NULL,
    liters REAL NOT NULL,
    cost REAL NOT NULL,
    station TEXT,
    odometer REAL
);

CREATE TABLE IF NOT EXISTS maintenance_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
    maintenance_type TEXT NOT NULL DEFAULT 'service'
        CHECK (maintenance_type IN ('service', 'repair', 'inspection', 'tyres', 'insurance')),
    description TEXT,
    started_at DATE NOT NULL,
    completed_at DATE,
    cost REAL NOT NULL DEFAULT 0,
    odometer REAL,
    status TEXT NOT NULL DEFAULT 'scheduled'
        CHECK (status IN ('scheduled', 'in_progress', 'completed')),
    next_due DATE
);
"""

SEED_VEHICLES = [
    ("SF-001", "Toyota", "Coaster", 2021, "bus", "diesel", 30, 84200, "available", "Staff shuttle"),
    ("SF-002", "Hyundai", "County", 2020, "bus", "diesel", 34, 121500, "in_service", "City route 12"),
    ("SF-003", "Toyota", "Hiace", 2022, "minibus", "diesel", 15, 45900, "available", "Airport shuttle"),
    ("SF-004", "Nissan", "Urvan", 2019, "minibus", "diesel", 13, 158300, "maintenance", "Gearbox repair"),
    ("SF-005", "Toyota", "Corolla", 2023, "car", "petrol", 4, 12400, "available", "Executive"),
    ("SF-006", "Isuzu", "NPR", 2018, "truck", "diesel", 2, 210700, "in_service", "Cargo delivery"),
]

SEED_DRIVERS = [
    ("DRV-001", "Ravi Perera", "+94 77 123 4567", "ravi@sahanfleet.com", "B1-458920", "2027-04-18", "on_trip", "2019-03-01"),
    ("DRV-002", "Sunil Silva", "+94 76 223 3445", "sunil@sahanfleet.com", "B1-512340", "2026-11-02", "available", "2020-07-15"),
    ("DRV-003", "Ayesha Fernando", "+94 75 998 8877", "ayesha@sahanfleet.com", "B1-663411", "2028-01-25", "available", "2021-01-10"),
    ("DRV-004", "Mohamed Careem", "+94 71 555 4433", "careem@sahanfleet.com", "B1-774502", "2026-10-30", "off_duty", "2018-05-20"),
    ("DRV-005", "Nimal Jayasuriya", "+94 70 334 2211", "nimal@sahanfleet.com", "B1-889123", "2027-08-14", "available", "2022-09-05"),
]

SEED_ROUTES = [
    ("City Loop", "Colombo Fort", "Colombo Fort", 28.5, 2.0),
    ("Airport Express", "Colombo Fort", "Bandaranaike Intl. Airport", 35.0, 1.0),
    ("Kandy Highway", "Colombo", "Kandy", 115.0, 3.5),
    ("Southern Coast", "Colombo", "Galle", 116.0, 3.0),
    ("Cargo - Negombo", "Colombo Warehouse", "Negombo", 40.0, 1.5),
]

SEED_FUEL = [
    (1, "FUEL-1001", "2026-08-02", 62.5, 34200, "Ceypetco Kotte", 81200),
    (2, "FUEL-1002", "2026-08-05", 70.0, 38150, "Ceypetco Kadawatha", 118400),
    (3, "FUEL-1003", "2026-08-11", 45.0, 24500, "S Lanka Katunayake", 44100),
    (5, "FUEL-1004", "2026-08-14", 38.0, 26600, "Shell Nugegoda", 11800),
    (6, "FUEL-1005", "2026-08-19", 95.0, 51800, "Ceypetco Kolonnawa", 208900),
    (1, "FUEL-1006", "2026-09-01", 58.0, 31900, "Ceypetco Kotte", 83100),
    (2, "FUEL-1007", "2026-09-04", 66.0, 36300, "Ceypetco Kadawatha", 120200),
    (3, "FUEL-1008", "2026-09-10", 41.5, 22800, "S Lanka Katunayake", 45300),
    (6, "FUEL-1009", "2026-09-15", 88.0, 48000, "Ceypetco Kolonnawa", 210100),
    (5, "FUEL-1010", "2026-09-18", 35.0, 24500, "Shell Nugegoda", 12250),
]

SEED_MAINTENANCE = [
    (1, "service", "10,000 km routine service", "2026-07-12", "2026-07-12", 42000, 80000, "completed", "2026-10-12"),
    (2, "tyres", "Replace 4 rear tyres", "2026-08-20", "2026-08-22", 186000, 119500, "completed", "2027-08-20"),
    (4, "repair", "Gearbox overhaul", "2026-09-12", None, 315000, 158300, "in_progress", None),
    (3, "inspection", "Annual fitness inspection", "2026-09-28", None, 15000, 45900, "scheduled", "2027-09-28"),
    (5, "insurance", "Comprehensive insurance renewal", "2026-10-05", None, 98000, None, "scheduled", "2027-10-05"),
    (6, "service", "Oil + filter change", "2026-09-08", "2026-09-08", 38000, 209800, "completed", "2026-12-08"),
]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def next_code(db, table, column, prefix):
    row = db.execute(
        f"SELECT {column} FROM {table} WHERE {column} LIKE ? ORDER BY id DESC LIMIT 1",
        (f"{prefix}%",),
    ).fetchone()
    if row is None:
        return f"{prefix}0001"
    digits = "".join(ch for ch in row[0] if ch.isdigit())
    return f"{prefix}{int(digits or 0) + 1:04d}"


def init_db():
    from .auth import hash_password

    db = get_db()
    db.executescript(SCHEMA)

    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        db.execute(
            "INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
            ("admin", hash_password("admin123"), "Fleet Administrator", "admin"),
        )
        db.executemany(
            """INSERT INTO vehicles
               (plate_no, make, model, year, vehicle_type, fuel_type, capacity,
                odometer, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            SEED_VEHICLES,
        )
        db.executemany(
            """INSERT INTO drivers
               (employee_no, name, phone, email, license_no, license_expiry, status, hired_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            SEED_DRIVERS,
        )
        db.executemany(
            """INSERT INTO routes (name, origin, destination, distance_km, estimated_hours)
               VALUES (?, ?, ?, ?, ?)""",
            SEED_ROUTES,
        )
        _seed_trips(db)
        _seed_bookings(db)
        db.executemany(
            """INSERT INTO fuel_records
               (vehicle_id, ref_no, filled_at, liters, cost, station, odometer)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            SEED_FUEL,
        )
        db.executemany(
            """INSERT INTO maintenance_records
               (vehicle_id, maintenance_type, description, started_at, completed_at,
                cost, odometer, status, next_due)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            SEED_MAINTENANCE,
        )
    db.commit()


def _seed_trips(db):
    trips = [
        ("TRIP-0001", 1, 1, 2, "2026-09-01 06:30", "2026-09-01 08:30", 28.5, "completed", 28000, 9500, "Morning staff loop"),
        ("TRIP-0002", 2, 3, 1, "2026-09-02 04:00", "2026-09-02 05:15", 35.0, "completed", 45000, 12000, "Airport express"),
        ("TRIP-0003", 3, 6, 4, "2026-09-03 07:00", "2026-09-03 09:00", 40.0, "completed", 62000, 18000, "Cargo to Negombo"),
        ("TRIP-0004", 1, 2, 3, "2026-09-10 06:30", "2026-09-10 08:30", 28.5, "completed", 30000, 10200, ""),
        ("TRIP-0005", 4, 5, 5, "2026-09-20 07:30", "2026-09-20 11:00", 116.0, "in_transit", 75000, 24000, "VIP to Galle"),
        ("TRIP-0006", 2, 3, 1, "2026-09-21 16:00", "2026-09-21 17:15", 35.0, "scheduled", 48000, 12500, "Evening arrival pickup"),
        ("TRIP-0007", 3, 1, 2, "2026-09-25 06:00", "2026-09-25 09:45", 115.0, "scheduled", 90000, 31000, "Kandy corporate group"),
        ("TRIP-0008", 1, 2, 3, "2026-09-08 06:30", "2026-09-08 08:30", 28.5, "cancelled", 0, 0, "Vehicle reallocated"),
    ]
    db.executemany(
        """INSERT INTO trips
           (trip_no, route_id, vehicle_id, driver_id, departure_at, arrival_at,
            distance_km, status, revenue, cost, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        trips,
    )


def _seed_bookings(db):
    bookings = [
        ("BK-0001", "Chathura Bandara", "+94 77 111 2222", 2, "Colombo Fort", "CMB Airport", 2, 9000, "completed"),
        ("BK-0002", "Dilini Opatha", "+94 76 333 4444", 2, "Kollupitiya", "CMB Airport", 1, 4500, "completed"),
        ("BK-0003", "Farhan Rasheed", "+94 75 555 6666", 5, "Colombo", "Galle", 3, 22500, "boarded"),
        ("BK-0004", "Nadeesha Kumari", "+94 71 777 8888", 6, "Fort", "CMB Airport", 1, 4500, "confirmed"),
        ("BK-0005", "Wickrama Silva", "+94 70 999 0000", 7, "Colombo", "Kandy", 4, 36000, "confirmed"),
        ("BK-0006", "Ishara Maduranga", "+94 77 246 8101", 7, "Nugegoda", "Kandy", 1, 9000, "pending"),
        ("BK-0007", "Ryan Cooray", "+94 76 135 7911", 1, "Battaramulla", "Fort", 5, 12500, "completed"),
        ("BK-0008", "Shani Wijesinghe", "+94 75 864 2102", 4, "Fort", "Dehiwala", 2, 6000, "completed"),
        ("BK-0009", "Nuwan Tharaka", "+94 71 420 6969", 6, "Fort", "CMB Airport", 2, 9000, "pending"),
        ("BK-0010", "Mariam Cader", "+94 70 777 1212", 3, "Negombo", "Colombo", 1, 3500, "cancelled"),
    ]
    db.executemany(
        """INSERT INTO bookings
           (booking_no, passenger_name, phone, trip_id, pickup, dropoff, seats, fare, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        bookings,
    )


@click.command("init-db")
def init_db_command():
    init_db()
    click.echo("Database initialised.")


@click.command("reset-db")
def reset_db_command():
    db = get_db()
    db.executescript(
        "DROP TABLE IF EXISTS users; DROP TABLE IF EXISTS bookings; DROP TABLE IF EXISTS trips;"
        "DROP TABLE IF EXISTS fuel_records; DROP TABLE IF EXISTS maintenance_records;"
        "DROP TABLE IF EXISTS vehicles; DROP TABLE IF EXISTS drivers; DROP TABLE IF EXISTS routes;"
    )
    db.commit()
    init_db()
    click.echo("Database reset and reseeded.")
