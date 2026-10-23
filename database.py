"""
iHANDA Dagupan - SQLite data layer (built-in sqlite3 only).

One database file holds: user + admin accounts, emergency reports (with their
history) and evacuation areas.  Every SQL statement is parameterized.

The file is created automatically the first time init_db() runs.
Default location : <this folder>/ihanda_dagupan.db
Override location: set the environment variable IHANDA_DB to a file path.
"""

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path


DB_PATH = Path(
    os.environ.get("IHANDA_DB")
    or Path(__file__).resolve().parent / "ihanda_dagupan.db"
)


# =========================================================
# CONSTANTS USED BY THE DATA LAYER
# =========================================================

PBKDF2_ITERATIONS = 600_000
USER_EMAIL_SUFFIX = ".ih@dagupan.com"
USER_EMAIL_EXAMPLE = "juan.ih@dagupan.com"

# local part (letters/digits, separated by . _ + -) + exactly ".ih@dagupan.com"
USER_EMAIL_RE = re.compile(
    r"[a-z0-9]+(?:[._+\-][a-z0-9]+)*\.ih@dagupan\.com"
)
GENERIC_EMAIL_RE = re.compile(r"[a-z0-9._%+\-]+@[a-z0-9\-]+(?:\.[a-z0-9\-]+)*\.[a-z]{2,}")
USERNAME_RE = re.compile(r"[A-Za-z0-9_.\-]{3,30}")

REPORT_STATUSES = ["Pending", "Verified", "In Progress", "Resolved"]
UNASSIGNED = "Unassigned"

RESPONSE_ORGANIZATIONS = [
    "Unassigned",
    "Barangay Officials / Barangay DRRM Committee",
    "Dagupan City Disaster Risk Reduction and Management Office (CDRRMO)",
    "Bureau of Fire Protection (BFP)",
    "Philippine National Police (PNP)",
    "Philippine Red Cross",
    "Philippine Coast Guard",
    "Other authorized emergency response organization"
]

DISPATCH_RECIPIENTS = [
    "CDRRMO",
    "Barangay Officials / Barangay DRRM Committee",
    "Bureau of Fire Protection (BFP)",
    "Philippine National Police (PNP)",
    "Philippine Coast Guard",
    "City Health Office / Medical Responders"
]

# Inserted only the very first time the database is created.
DEFAULT_EVACUATION_AREAS = [
    ("Dagupan City Astrodome", "Pantal", "Pantal, Dagupan City", "500",
     "Follow official evacuation instructions."),
    ("West Central Elementary School", "Poblacion Oeste",
     "Poblacion Oeste, Dagupan City", "250",
     "Use only when officially designated.")
]

DELIVERY_NOTE = (
    "Saved locally in this system (not transmitted to any organization)"
)


# =========================================================
# CONNECTION + SCHEMA
# =========================================================

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'user'
                  CHECK (role IN ('user', 'admin')),
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL,
    last_login    TEXT
);

CREATE TABLE IF NOT EXISTS reports (
    report_id             TEXT PRIMARY KEY,
    user_id               INTEGER REFERENCES users(id) ON DELETE SET NULL,
    name                  TEXT NOT NULL,
    contact               TEXT NOT NULL,
    barangay              TEXT NOT NULL,
    location              TEXT NOT NULL,
    emergency             TEXT NOT NULL,
    description           TEXT NOT NULL,
    photo                 TEXT NOT NULL DEFAULT '',
    date_time             TEXT NOT NULL,
    submitted_iso         TEXT NOT NULL,
    status                TEXT NOT NULL DEFAULT 'Pending',
    assigned_organization TEXT NOT NULL DEFAULT 'Unassigned',
    response_notes        TEXT NOT NULL DEFAULT '',
    completed_at          TEXT NOT NULL DEFAULT '',
    sent_to_officials     TEXT NOT NULL DEFAULT '',
    sent_to_officials_at  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS report_history (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id TEXT NOT NULL REFERENCES reports(report_id) ON DELETE CASCADE,
    entry     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_report_history_report
    ON report_history(report_id);

CREATE TABLE IF NOT EXISTS evacuation_areas (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL,
    barangay TEXT NOT NULL,
    location TEXT NOT NULL DEFAULT '',
    capacity TEXT NOT NULL DEFAULT '',
    notes    TEXT NOT NULL DEFAULT ''
);
"""


def connect():
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db():
    """Open a connection, commit on success, roll back on error, close."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create the database file and all tables if they do not exist yet."""
    first_time = not DB_PATH.exists()

    with db() as conn:
        conn.executescript(SCHEMA)

        # user_version 0 = brand new database -> add the default areas once.
        # (Afterwards the admin may delete them without them coming back.)
        if conn.execute("PRAGMA user_version").fetchone()[0] < 1:
            conn.executemany(
                "INSERT INTO evacuation_areas "
                "(name, barangay, location, capacity, notes) "
                "VALUES (?, ?, ?, ?, ?)",
                DEFAULT_EVACUATION_AREAS
            )
            conn.execute("PRAGMA user_version = 1")

    if first_time:
        try:
            os.chmod(DB_PATH, 0o600)      # owner only (ignored on Windows)
        except OSError:
            pass


# =========================================================
# PASSWORDS  (salted PBKDF2-HMAC-SHA256, never plain text)
# =========================================================

def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password, stored):
    try:
        scheme, iterations, salt_hex, hash_hex = stored.split("$")

        if scheme != "pbkdf2_sha256":
            return False

        expected = bytes.fromhex(hash_hex)
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"),
            bytes.fromhex(salt_hex), int(iterations)
        )
    except (ValueError, AttributeError):
        return False

    return hmac.compare_digest(candidate, expected)


_DUMMY = {}


def _dummy_hash():
    """Used so an unknown username takes as long to reject as a wrong password."""
    if "hash" not in _DUMMY:
        _DUMMY["hash"] = hash_password(secrets.token_hex(8))
    return _DUMMY["hash"]


def validate_password(password):
    """Return an error message, or '' if the password is acceptable."""
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if len(password) > 128:
        return "Password must be 128 characters or fewer."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Password must contain both letters and numbers."
    return ""


# =========================================================
# EMAIL / USERNAME RULES
# =========================================================

def normalize_email(email):
    return (email or "").strip().lower()


def validate_user_email(email):
    """Public-registration email. Returns (normalized_email, error)."""
    email = normalize_email(email)

    if (
        len(email) > 254 or
        USER_EMAIL_RE.fullmatch(email) is None
    ):
        return email, (
            "Invalid email address. Use your iHANDA email ending in "
            f"{USER_EMAIL_SUFFIX} (example: {USER_EMAIL_EXAMPLE})."
        )

    return email, ""


def validate_generic_email(email):
    """Admin account email (any normal address). Returns (email, error)."""
    email = normalize_email(email)

    if len(email) > 254 or GENERIC_EMAIL_RE.fullmatch(email) is None:
        return email, "Invalid email address."

    return email, ""


def validate_username(username):
    if USERNAME_RE.fullmatch(username) is None:
        return (
            "Username must be 3-30 characters and may only contain "
            "letters, numbers, dots, dashes and underscores."
        )
    return ""


# =========================================================
# ACCOUNTS
# =========================================================

def now_text():
    return datetime.now().strftime("%B %d, %Y | %I:%M %p")


def _create_account(username, email, password, confirm, role, email_rule):
    """Shared validation + insert. Returns (ok, message)."""
    username = (username or "").strip()
    email = (email or "").strip()
    password = password or ""
    confirm = confirm or ""

    missing = [
        label for label, value in (
            ("username", username),
            ("email", email),
            ("password", password),
            ("password confirmation", confirm)
        ) if not value
    ]

    if missing:
        if len(missing) > 1:
            missing = [", ".join(missing[:-1]) + " and " + missing[-1]]

        return False, (
            "Missing information. Please enter your " + missing[0] + "."
        )

    error = validate_username(username)
    if error:
        return False, error

    email, error = email_rule(email)
    if error:
        return False, error

    error = validate_password(password)
    if error:
        return False, error

    if password != confirm:
        return False, "Passwords do not match."

    try:
        with db() as conn:
            if conn.execute(
                "SELECT 1 FROM users WHERE username = ?", (username,)
            ).fetchone():
                return False, (
                    "That username is already taken. "
                    "Please choose another one."
                )

            if conn.execute(
                "SELECT 1 FROM users WHERE email = ?", (email,)
            ).fetchone():
                return False, (
                    "An account with that email address already exists."
                )

            conn.execute(
                "INSERT INTO users "
                "(username, email, password_hash, role, is_active, created_at) "
                "VALUES (?, ?, ?, ?, 1, ?)",
                (username, email, hash_password(password), role, now_text())
            )
    except sqlite3.IntegrityError:
        return False, "That username or email address is already registered."

    return True, "Account created successfully."


def register_user(username, email, password, confirm):
    """PUBLIC registration. Always creates a plain 'user' - never an admin."""
    return _create_account(
        username, email, password, confirm, "user", validate_user_email
    )


def create_admin_account(username, email, password, confirm):
    """Only called by setup_admin.py (terminal). Creates a role='admin' row."""
    return _create_account(
        username, email, password, confirm, "admin", validate_generic_email
    )


def admin_exists():
    with db() as conn:
        return conn.execute(
            "SELECT 1 FROM users WHERE role = 'admin' LIMIT 1"
        ).fetchone() is not None


# ----- login with a small brute-force lock -----

_FAILURES = {}
MAX_ATTEMPTS = 5
LOCK_SECONDS = 30


def _lock_remaining(key):
    count, until = _FAILURES.get(key, (0, 0))
    remaining = int(until - time.time())
    return remaining if remaining > 0 else 0


def _register_failure(key):
    count, until = _FAILURES.get(key, (0, 0))
    count += 1

    if count >= MAX_ATTEMPTS:
        _FAILURES[key] = (0, time.time() + LOCK_SECONDS)
    else:
        _FAILURES[key] = (count, 0)


def authenticate(identifier, password, role):
    """
    Check a username-or-email + password for the given portal
    (role = 'user' or 'admin').  Returns (user_dict, "") or (None, message).
    """
    identifier = (identifier or "").strip()
    password = password or ""

    if not identifier or not password:
        return None, (
            "Missing information. Please enter your username or email "
            "and your password."
        )

    key = role + ":" + identifier.lower()
    remaining = _lock_remaining(key)

    if remaining:
        return None, (
            f"Too many failed attempts. Please wait {remaining} seconds "
            "and try again."
        )

    with db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? OR email = ?",
            (identifier, identifier.lower())
        ).fetchone()

        valid = verify_password(
            password, row["password_hash"] if row else _dummy_hash()
        )

        if row is None or not valid:
            _register_failure(key)
            return None, "Incorrect username/email or password."

        if not row["is_active"]:
            return None, "This account has been deactivated."

        if row["role"] != role:
            if role == "user":
                return None, (
                    "This account cannot sign in here. "
                    "Please use the correct application."
                )
            return None, "This account does not have administrator access."

        _FAILURES.pop(key, None)

        conn.execute(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (now_text(), row["id"])
        )

        user = {
            "id": row["id"],
            "username": row["username"],
            "email": row["email"],
            "role": row["role"]
        }

    return user, ""


# =========================================================
# ADMIN SESSION  (only the admin application ever sets this)
# =========================================================

ADMIN_SESSION = {"id": None}


def start_admin_session(user):
    if not user or user.get("role") != "admin":
        raise PermissionError("Administrator login required.")

    ADMIN_SESSION["id"] = user["id"]


def end_admin_session():
    ADMIN_SESSION["id"] = None


def admin_session_valid():
    """True only if a session exists AND that account is still an active admin."""
    user_id = ADMIN_SESSION["id"]

    if user_id is None:
        return False

    with db() as conn:
        row = conn.execute(
            "SELECT 1 FROM users "
            "WHERE id = ? AND role = 'admin' AND is_active = 1",
            (user_id,)
        ).fetchone()

    if row is None:
        ADMIN_SESSION["id"] = None
        return False

    return True


def require_admin():
    """Every admin-only function starts with this."""
    if not admin_session_valid():
        raise PermissionError("Administrator login required.")


# =========================================================
# REPORTS
# =========================================================

def _add_history(conn, report_id, text):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO report_history (report_id, entry) VALUES (?, ?)",
        (report_id, f"[{stamp}] {text}")
    )


def _new_report_id(conn):
    prefix = "IH-" + datetime.now().strftime("%Y%m%d") + "-"
    number = conn.execute(
        "SELECT COUNT(*) FROM reports WHERE report_id LIKE ?",
        (prefix + "%",)
    ).fetchone()[0] + 1

    while conn.execute(
        "SELECT 1 FROM reports WHERE report_id = ?",
        (f"{prefix}{number:04d}",)
    ).fetchone():
        number += 1

    return f"{prefix}{number:04d}"


def _get_report(conn, report_id):
    row = conn.execute(
        "SELECT * FROM reports WHERE report_id = ?", (report_id,)
    ).fetchone()

    if row is None:
        return None

    report = dict(row)
    report["history"] = [
        h["entry"] for h in conn.execute(
            "SELECT entry FROM report_history WHERE report_id = ? ORDER BY id",
            (report_id,)
        )
    ]
    return report


def find_report(report_id):
    require_admin()

    with db() as conn:
        return _get_report(conn, report_id)


def get_all_reports():
    require_admin()

    with db() as conn:
        rows = conn.execute("SELECT * FROM reports").fetchall()
        history = {}

        for h in conn.execute(
            "SELECT report_id, entry FROM report_history ORDER BY id"
        ):
            history.setdefault(h["report_id"], []).append(h["entry"])

    reports = []

    for row in rows:
        report = dict(row)
        report["history"] = history.get(report["report_id"], [])
        reports.append(report)

    return reports


def find_duplicate(data, user_id):
    """An unresolved report from the same user with identical content."""
    keys = ("name", "contact", "barangay", "location",
            "emergency", "description")

    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM reports WHERE user_id = ? AND status != 'Resolved'",
            (user_id,)
        ).fetchall()

    for row in rows:
        if all(str(row[k]).lower() == str(data[k]).lower() for k in keys):
            return dict(row)

    return None


def create_report(data, user_id):
    """Save a new report for a logged-in user."""
    with db() as conn:
        if conn.execute(
            "SELECT 1 FROM users WHERE id = ? AND is_active = 1", (user_id,)
        ).fetchone() is None:
            raise PermissionError("Please log in to submit a report.")

        report_id = _new_report_id(conn)
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn.execute(
            "INSERT INTO reports (report_id, user_id, name, contact, barangay, "
            "location, emergency, description, photo, date_time, "
            "submitted_iso, status, assigned_organization) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', ?)",
            (
                report_id, user_id, data["name"], data["contact"],
                data["barangay"], data["location"], data["emergency"],
                data["description"], data["photo"], now_text(), stamp,
                UNASSIGNED
            )
        )
        _add_history(conn, report_id, "Report created. " + DELIVERY_NOTE + ".")

        return _get_report(conn, report_id)


def update_report(report_id, status, organization, notes):
    """Update status / organization / notes. Returns (ok, message)."""
    require_admin()

    notes = notes.strip() if notes else ""

    with db() as conn:
        report = _get_report(conn, report_id)

        if report is None:
            return False, "Report not found."

        if status not in REPORT_STATUSES:
            return False, "Please select a valid status."

        if organization not in RESPONSE_ORGANIZATIONS:
            return False, "Please select a valid organization."

        if status in ("In Progress", "Resolved") and organization == UNASSIGNED:
            return False, (
                "Please assign an organization before setting the status to "
                f"'{status}'."
            )

        if len(notes) > 1000:
            return False, "Response notes must be 1000 characters or fewer."

        old_status = report["status"]
        completed_at = report["completed_at"]
        changed = False
        message = "Report updated successfully."

        if status != old_status:
            _add_history(
                conn, report_id, f"Status changed: {old_status} -> {status}"
            )
            changed = True

            if status == "Resolved":
                completed_at = now_text()
                _add_history(
                    conn, report_id,
                    "Response completed. Moved to Response Archive."
                )
                message = (
                    "Report marked as Resolved and moved to the "
                    "Response Archive."
                )
            elif old_status == "Resolved":
                _add_history(
                    conn, report_id,
                    "Report reopened (previously completed on "
                    f"{report['completed_at'] or 'unknown date'})."
                )
                completed_at = ""
                message = "Report reopened and returned to Active Reports."

        if organization != report["assigned_organization"]:
            _add_history(
                conn, report_id,
                "Assigned organization: "
                f"{report['assigned_organization']} -> {organization}"
            )
            changed = True

        if notes != report["response_notes"]:
            _add_history(
                conn, report_id,
                "Response notes updated: "
                + (" ".join(notes.split())[:120] if notes else "(cleared)")
            )
            changed = True

        if not changed:
            return True, "No changes to save."

        conn.execute(
            "UPDATE reports SET status = ?, assigned_organization = ?, "
            "response_notes = ?, completed_at = ? WHERE report_id = ?",
            (status, organization, notes, completed_at, report_id)
        )

    return True, message


def reopen_report(report_id):
    """Move an archived report back to Active Reports. Returns (ok, message)."""
    require_admin()

    with db() as conn:
        report = _get_report(conn, report_id)

        if report is None:
            return False, "Report not found."

        if report["status"] != "Resolved":
            return False, "Only archived (Resolved) reports can be reopened."

        _add_history(
            conn, report_id,
            "Report reopened (previously completed on "
            f"{report['completed_at'] or 'unknown date'}). "
            "Status: In Progress"
        )
        conn.execute(
            "UPDATE reports SET status = 'In Progress', completed_at = '' "
            "WHERE report_id = ?",
            (report_id,)
        )

    return True, "Report reopened and returned to Active Reports."


def dispatch_report(report_id, recipients):
    """SIMULATED dispatch. Nobody is contacted. Returns (ok, message)."""
    require_admin()

    with db() as conn:
        report = _get_report(conn, report_id)

        if report is None:
            return False, "Report not found."

        if report["status"] == "Resolved":
            return False, (
                "Archived reports cannot be dispatched. Reopen it first."
            )

        if report["sent_to_officials"]:
            return False, (
                "This report was already marked as sent in the simulation."
            )

        recipients = [r for r in recipients if r in DISPATCH_RECIPIENTS]

        if not recipients:
            return False, "Select at least one official or agency first."

        text = ", ".join(recipients)

        conn.execute(
            "UPDATE reports SET sent_to_officials = ?, "
            "sent_to_officials_at = ? WHERE report_id = ?",
            (text, now_text(), report_id)
        )
        _add_history(conn, report_id, f"SIMULATED response dispatch to {text}")

    return True, text


def filter_reports(mode, text="", rtype="", status="", org="", date=""):
    """mode: 'active', 'archive' or 'all'. Newest first. (admin only)"""
    text = text.lower().strip()
    result = []

    for r in get_all_reports():
        resolved = r["status"] == "Resolved"

        if mode == "active" and resolved:
            continue
        if mode == "archive" and not resolved:
            continue
        if rtype and r["emergency"] != rtype:
            continue
        if status and r["status"] != status:
            continue
        if org and r["assigned_organization"] != org:
            continue
        if date and not r["submitted_iso"].startswith(date):
            continue
        if text:
            haystack = " ".join(
                str(r[k]) for k in (
                    "report_id", "name", "barangay", "location",
                    "emergency", "description", "response_notes",
                    "assigned_organization"
                )
            ).lower()
            if text not in haystack:
                continue

        result.append(r)

    result.sort(
        key=lambda r: (r["submitted_iso"], r["report_id"]), reverse=True
    )
    return result


# =========================================================
# EVACUATION AREAS  (read: everyone / change: admin only)
# =========================================================

AREA_FIELDS = ("name", "barangay", "location", "capacity", "notes")


def get_evacuation_areas():
    with db() as conn:
        rows = conn.execute(
            "SELECT id, name, barangay, location, capacity, notes "
            "FROM evacuation_areas ORDER BY id"
        ).fetchall()

    return [dict(r) for r in rows]


def _clean_area(values):
    clean = {k: str(values.get(k, "")).strip() for k in AREA_FIELDS}

    if not clean["name"] or not clean["barangay"]:
        return None, "Location Name and Barangay are required."

    if not clean["capacity"].isdigit() or int(clean["capacity"]) < 1:
        return None, "Capacity must be a number greater than 0."

    clean["capacity"] = str(int(clean["capacity"]))
    return clean, ""


def add_evacuation_area(values):
    require_admin()
    clean, error = _clean_area(values)

    if error:
        return False, error

    with db() as conn:
        conn.execute(
            "INSERT INTO evacuation_areas "
            "(name, barangay, location, capacity, notes) "
            "VALUES (?, ?, ?, ?, ?)",
            tuple(clean[k] for k in AREA_FIELDS)
        )

    return True, "Evacuation area added."


def update_evacuation_area(area_id, values):
    require_admin()
    clean, error = _clean_area(values)

    if error:
        return False, error

    with db() as conn:
        cursor = conn.execute(
            "UPDATE evacuation_areas SET name = ?, barangay = ?, "
            "location = ?, capacity = ?, notes = ? WHERE id = ?",
            tuple(clean[k] for k in AREA_FIELDS) + (area_id,)
        )

    if cursor.rowcount == 0:
        return False, "Evacuation area not found."

    return True, "Evacuation area updated."


def delete_evacuation_area(area_id):
    require_admin()

    with db() as conn:
        cursor = conn.execute(
            "DELETE FROM evacuation_areas WHERE id = ?", (area_id,)
        )

    if cursor.rowcount == 0:
        return False, "Evacuation area not found."

    return True, "Evacuation area deleted."
