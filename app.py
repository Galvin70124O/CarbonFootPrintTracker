import csv
import io
import json
import os
import secrets
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import (Flask, Response, flash, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import db as database

BASE_DIR = Path(__file__).resolve().parent
IS_PRODUCTION = os.environ.get("ENVIRONMENT") == "production" or bool(os.environ.get("RENDER"))
APP_TZ = ZoneInfo(os.environ.get("APP_TIMEZONE", "Asia/Kolkata"))
MIN_PASSWORD_LENGTH = 8

app = Flask(__name__)

secret_key = os.environ.get("SECRET_KEY")
if not secret_key:
    if IS_PRODUCTION:
        raise RuntimeError("SECRET_KEY must be set in production")
    # Dev only: a fresh key per run (you get logged out on restart).
    secret_key = secrets.token_hex(32)
app.config.update(
    SECRET_KEY=secret_key,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=IS_PRODUCTION,
    PERMANENT_SESSION_LIFETIME=timedelta(days=14),
)


# ---------- CSRF ----------
def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def check_csrf():
    if request.method in ("GET", "HEAD", "OPTIONS") or app.config.get("CSRF_DISABLED"):
        return None
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token", "")
    expected = session.get("_csrf", "")
    if not expected or not secrets.compare_digest(sent, expected):
        if request.is_json:
            return {"ok": False, "error": "Invalid or missing CSRF token"}, 400
        flash("Your session expired. Please try again.", "error")
        ref = request.referrer or ""
        return redirect(ref if ref.startswith(request.host_url) else url_for("index"))
    return None


# ---------- EMISSION FACTORS ----------
def load_factors():
    with open(BASE_DIR / "emissions.json", encoding="utf-8") as f:
        return json.load(f)


FACTORS = load_factors()
CATEGORIES = FACTORS["categories"]
GRID = FACTORS["grid_kg_per_kwh"]
INDIA_DAILY_KG = FACTORS["india_avg_tonnes_per_year"] * 1000 / 365
ITEM_TO_CATEGORY = {item: cat for cat, c in CATEGORIES.items() for item in c["items"]}


def item_unit(category, item):
    return CATEGORIES[category]["items"][item].get("unit", CATEGORIES[category]["unit"])


def calculate_emission(category, item, amount, mode="weight"):
    """Return (kg CO2e, unit label) for an activity, or raise ValueError."""
    if category not in CATEGORIES or item not in CATEGORIES[category]["items"]:
        raise ValueError("Unknown activity")
    if amount <= 0:
        raise ValueError("Amount must be more than zero")
    spec = CATEGORIES[category]["items"][item]

    if category == "energy":
        kg = amount * spec["power_kw"] * GRID
        unit = item_unit(category, item)
    elif category == "food" and mode == "servings":
        kg = amount * spec["serving_kg"] * spec["factor"]
        unit = "servings"
    else:
        kg = amount * spec["factor"]
        unit = item_unit(category, item)
    return round(kg, 4), unit


def label_for(category, item):
    try:
        return CATEGORIES[category]["items"][item]["label"]
    except KeyError:
        return item.replace("_", " ").title()


# ---------- DATABASE ----------
def get_db():
    if "db" not in g:
        g.db = database.connect()
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def migrate_old_rows(db):
    """Fix rows saved by the old /add route: category = item, unit = "units",
    and full ISO timestamps instead of dates."""
    rows = db.query("SELECT id, activity_type, amount, date FROM activities WHERE unit = 'units'")
    for r in rows:
        item = r["activity_type"]
        cat = ITEM_TO_CATEGORY.get(item)
        if not cat:
            continue
        kg, unit = calculate_emission(cat, item, r["amount"])
        db.execute(
            "UPDATE activities SET category = ?, unit = ?, emission = ?, date = ? WHERE id = ?",
            (cat, unit, kg, str(r["date"])[:10], r["id"]),
        )
    db.execute("UPDATE activities SET date = SUBSTR(date, 1, 10) WHERE LENGTH(date) > 10")
    db.commit()


def init_db():
    conn = database.connect()
    try:
        database.init_schema(conn)
        migrate_old_rows(conn)
    finally:
        conn.close()


init_db()


# ---------- HELPERS ----------
def today():
    return datetime.now(APP_TZ).date()


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return wrapper


@app.context_processor
def inject_globals():
    return {"is_authenticated": "user_id" in session, "username": session.get("username")}


@app.after_request
def security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if IS_PRODUCTION:
        resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return resp


def parse_date(raw):
    if not raw:
        return today()
    d = date.fromisoformat(raw)
    if d > today():
        raise ValueError("Date can't be in the future")
    if d.year < 2000:
        raise ValueError("Date is too far in the past")
    return d


def safe_next(target):
    return target if target and target.startswith("/") and not target.startswith("//") else None


def build_stats(user_id):
    db = get_db()
    t = today()
    start30 = t - timedelta(days=29)
    month_start = t.replace(day=1)

    rows30 = db.query(
        "SELECT date, category, emission FROM activities WHERE user_id = ? AND date >= ?",
        (user_id, start30.isoformat()),
    )
    totals = db.one(
        "SELECT COUNT(*) AS n, COALESCE(SUM(emission), 0) AS total, MIN(date) AS first "
        "FROM activities WHERE user_id = ?",
        (user_id,),
    )

    daily = {(start30 + timedelta(days=i)).isoformat(): 0.0 for i in range(30)}
    by_cat = {c: 0.0 for c in CATEGORIES}
    week_total = 0.0
    for r in rows30:
        d = str(r["date"])[:10]
        if d in daily:
            daily[d] += r["emission"]
        by_cat[r["category"]] = by_cat.get(r["category"], 0) + r["emission"]
        if d >= (t - timedelta(days=6)).isoformat():
            week_total += r["emission"]
    # This month can start before the 30-day window, so query it on its own.
    month_total = db.one(
        "SELECT COALESCE(SUM(emission), 0) AS s FROM activities WHERE user_id = ? AND date >= ?",
        (user_id, month_start.isoformat()),
    )["s"]

    # Average per day since the user started tracking (max 30 days), so a
    # new user isn't averaged over days they never logged.
    if totals["first"]:
        first = date.fromisoformat(str(totals["first"])[:10])
        days_tracked = max(1, min(30, (t - max(first, start30)).days + 1))
    else:
        days_tracked = 0
    sum30 = sum(daily.values())
    daily_avg = sum30 / days_tracked if days_tracked else 0

    user = db.one("SELECT monthly_goal FROM users WHERE id = ?", (user_id,))
    goal = user["monthly_goal"] if user else None

    return {
        "count": totals["n"],
        "all_time": round(totals["total"], 2),
        "month_total": round(month_total, 2),
        "week_total": round(week_total, 2),
        "daily_avg": round(daily_avg, 2),
        "india_daily": round(INDIA_DAILY_KG, 2),
        "vs_india_pct": round(daily_avg / INDIA_DAILY_KG * 100) if days_tracked else None,
        "goal": goal,
        "goal_pct": round(month_total / goal * 100) if goal else None,
        "month_name": t.strftime("%B"),
        "chart": {
            "labels": [datetime.fromisoformat(d).strftime("%d %b") for d in daily],
            "values": [round(v, 3) for v in daily.values()],
            "categories": [CATEGORIES[c]["label"] if c in CATEGORIES else c for c in by_cat],
            "categoryValues": [round(v, 3) for v in by_cat.values()],
        },
        "by_cat": by_cat,
        "tips": make_tips(by_cat, daily_avg, days_tracked),
    }


TIPS = {
    "transport": "Transport is your biggest source. Swap a few car trips for the bus, metro or a two-wheeler and it drops fast.",
    "energy": "Energy is your biggest source. Setting the AC to 24-26 °C and switching off the PC when idle cut the most.",
    "food": "Food is your biggest source. Beef is about 10x chicken per kg and mutton about 4x, so swapping a few of those meals helps most.",
    "waste": "Waste is your biggest source. Sorting recyclables and carrying your own bottle and bag reduces it.",
}


def make_tips(by_cat, daily_avg, days_tracked):
    if not days_tracked:
        return ["Log your first activity to see where your emissions come from."]
    tips = []
    top = max(by_cat, key=by_cat.get)
    if by_cat[top] > 0:
        tips.append(TIPS.get(top, ""))
    if daily_avg < INDIA_DAILY_KG:
        tips.append("Your daily average is below the India per-person average. Keep logging to see the trend.")
    else:
        tips.append("Your daily average is above the India per-person average. Set a monthly goal to keep it in check.")
    return [t for t in tips if t]


# ---------- PAGES ----------
@app.route("/")
def index():
    return render_template("index.html", categories=CATEGORIES)


@app.route("/landing")
def landing():
    return redirect(url_for("index"), code=301)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", password)

        error = None
        if not username or not password:
            error = "Please fill in all fields."
        elif not 3 <= len(username) <= 30:
            error = "Username must be 3 to 30 characters."
        elif len(password) < MIN_PASSWORD_LENGTH:
            error = f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        elif password != confirm:
            error = "Passwords don't match."

        if error:
            flash(error, "error")
            return render_template("register.html", username=username), 400

        db = get_db()
        try:
            db.execute("INSERT INTO users (username, password) VALUES (?, ?)",
                       (username, generate_password_hash(password)))
            db.commit()
        except database.IntegrityError:
            db.rollback()
            flash("That username is taken.", "error")
            return render_template("register.html", username=username), 400
        flash("Account created. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().one("SELECT * FROM users WHERE username = ?", (username,))
        if user and check_password_hash(user["password"], password):
            session.clear()  # new session (and CSRF token) on login
            session.permanent = True
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(safe_next(request.args.get("next")) or url_for("dashboard"))
        flash("Invalid username or password.", "error")
        return render_template("login.html", username=username), 401
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    uid = session["user_id"]
    recent = get_db().query(
        "SELECT * FROM activities WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT 8", (uid,))
    return render_template(
        "dashboard.html",
        stats=build_stats(uid),
        recent=[decorate(a) for a in recent],
        categories=CATEGORIES,
        today=today().isoformat(),
        grid=GRID,
    )


@app.route("/activities")
@login_required
def activities():
    cat = request.args.get("category", "")
    sql = "SELECT * FROM activities WHERE user_id = ?"
    params = [session["user_id"]]
    if cat in CATEGORIES:
        sql += " AND category = ?"
        params.append(cat)
    sql += " ORDER BY date DESC, id DESC"
    rows = [decorate(a) for a in get_db().query(sql, params)]
    return render_template("activities.html", activities=rows, categories=CATEGORIES,
                           selected=cat, total=round(sum(a["emission"] for a in rows), 2))


@app.route("/insights")
@login_required
def insights():
    return redirect(url_for("dashboard") + "#insights")


def decorate(a):
    a = dict(a)
    a["label"] = label_for(a["category"], a["activity_type"])
    a["category_label"] = CATEGORIES.get(a["category"], {}).get("label", a["category"].title())
    a["date"] = str(a["date"])[:10]
    d = date.fromisoformat(a["date"])
    a["date_label"] = d.strftime("%d %b") if d.year == today().year else d.strftime("%d %b %Y")
    return a


# ---------- ACTIONS ----------
@app.route("/add", methods=["POST"])
@login_required
def add_activity():
    data = request.get_json(silent=True) or request.form
    category = data.get("category", "")
    item = data.get("type") or data.get("activity_type", "")
    mode = data.get("mode", "weight")
    try:
        amount = float(data.get("amount", 0))
        activity_date = parse_date(data.get("date"))
        kg, unit = calculate_emission(category, item, amount, mode)
    except (TypeError, ValueError) as e:
        msg = str(e) if str(e) and "could not convert" not in str(e) else "Please enter a valid amount."
        if request.is_json:
            return {"ok": False, "error": msg}, 400
        flash(msg, "error")
        return redirect(url_for("dashboard"))

    db = get_db()
    db.execute(
        "INSERT INTO activities (user_id, category, activity_type, amount, unit, emission, date) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (session["user_id"], category, item, amount, unit, kg, activity_date.isoformat()),
    )
    db.commit()
    if request.is_json:
        return {"ok": True, "emission": kg}
    flash(f"Added {label_for(category, item)}: {kg:g} kg CO₂e.", "success")
    return redirect(url_for("dashboard"))


@app.route("/delete/<int:activity_id>", methods=["POST"])
@login_required
def delete_activity(activity_id):
    db = get_db()
    db.execute("DELETE FROM activities WHERE id = ? AND user_id = ?", (activity_id, session["user_id"]))
    db.commit()
    flash("Activity deleted.", "success")
    return redirect(safe_next(request.form.get("next")) or url_for("dashboard"))


@app.route("/goal", methods=["POST"])
@login_required
def set_goal():
    raw = request.form.get("monthly_goal", "").strip()
    try:
        goal = float(raw) if raw else None
        if goal is not None and goal <= 0:
            raise ValueError
    except ValueError:
        flash("Goal must be a positive number of kg.", "error")
        return redirect(url_for("dashboard"))
    db = get_db()
    db.execute("UPDATE users SET monthly_goal = ? WHERE id = ?", (goal, session["user_id"]))
    db.commit()
    flash("Monthly goal saved." if goal else "Monthly goal removed.", "success")
    return redirect(url_for("dashboard"))


@app.route("/export.csv")
@login_required
def export_csv():
    rows = get_db().query(
        "SELECT date, category, activity_type, amount, unit, emission FROM activities "
        "WHERE user_id = ? ORDER BY date, id", (session["user_id"],))
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["date", "category", "activity", "amount", "unit", "kg_co2e"])
    for r in rows:
        w.writerow([str(r["date"])[:10], r["category"], label_for(r["category"], r["activity_type"]),
                    r["amount"], r["unit"], r["emission"]])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=carbon-footprint-{today()}.csv"})


@app.route("/healthz")
def healthz():
    return {"ok": True}


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG") == "1"
    # Keep the Werkzeug debugger off the network unless HOST says otherwise.
    app.run(
        host=os.environ.get("HOST", "127.0.0.1" if debug else "0.0.0.0"),
        port=int(os.environ.get("PORT", 5000)),
        debug=debug,
    )
