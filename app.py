import os
import sqlite3
import json
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "carbon_tracker_secret_key_2024")

DATABASE = "carbon_tracker.db"

# ---------- DATABASE ----------
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        activity_type TEXT NOT NULL,
        amount REAL NOT NULL,
        unit TEXT NOT NULL,
        emission REAL NOT NULL,
        date TEXT NOT NULL,
        manual_date TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)
    conn.commit()
    conn.close()

init_db()

# ---------- AUTH DECORATOR ----------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return wrapper

# ---------- EMISSION CALCULATOR ----------
def load_emission_factors():
    try:
        with open("emissions.json", "r") as f:
            return json.load(f)
    except:
        return {
            "electricity": {"fan": 0.00005, "ac": 0.0008, "lights": 0.00006, "heater": 0.0007, "fridge": 0.00015},
            "transport": {"car": 0.00019, "bus": 0.00008, "train": 0.00004, "flight": 0.00025, "bike": 0, "walk": 0},
            "food": {"rice": {"per_serving": 0.0012, "per_kg": 1.2}, "chicken": {"per_serving": 0.0045, "per_kg": 4.5}, "beef": {"per_serving": 0.015, "per_kg": 15}, "pork": {"per_serving": 0.007, "per_kg": 7}, "vegetables": {"per_serving": 0.0002, "per_kg": 0.2}},
            "waste": {"landfill": 0.0005, "recycled": 0.0001, "composted": 0.00005}
        }

def calculate_emission(category, activity_type, amount, unit):
    factors = load_emission_factors()
    
    if category not in factors:
        return 0
    
    if category == "food":
        food_data = factors["food"].get(activity_type, {"per_serving": 0, "per_kg": 0})
        if unit in ["serving", "servings"]:
            return round(amount * food_data["per_serving"], 4)
        else:
            return round(amount * food_data["per_kg"] / 1000, 4)
    
    factor = factors[category].get(activity_type, 0)
    return round(amount * factor, 4)

# ---------- ROUTES ----------

@app.route("/")
def index():
    is_auth = "user_id" in session
    return render_template("index.html", is_authenticated=is_auth)

@app.route("/landing")
def landing():
    return render_template("landing.html", is_authenticated=("user_id" in session))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        if not username or not password:
            flash("Please fill in all fields", "error")
            return render_template("register.html", is_authenticated=False)
        
        if len(password) < 4:
            flash("Password must be at least 4 characters", "error")
            return render_template("register.html", is_authenticated=False)
        
        hashed_password = generate_password_hash(password)
        
        conn = get_db()
        try:
            conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", 
                        (username, hashed_password))
            conn.commit()
            flash("Registration successful! Please login.", "success")
            return redirect("/login")
        except sqlite3.IntegrityError:
            flash("Username already exists", "error")
        finally:
            conn.close()
    
    return render_template("register.html", is_authenticated=False)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        if not username or not password:
            flash("Please fill in all fields", "error")
            return render_template("login.html", is_authenticated=False)
        
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect("/dashboard")
        else:
            flash("Invalid username or password", "error")
    
    return render_template("login.html", is_authenticated=False)

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    
    # Get all activities for user
    activities = conn.execute(
        "SELECT * FROM activities WHERE user_id = ? ORDER BY date DESC",
        (session["user_id"],)
    ).fetchall()
    
    # Calculate total emissions
    total_emission = sum([a["emission"] for a in activities])
    
    # Get weekly data (last 7 days)
    weekly_data = conn.execute("""
        SELECT date, SUM(emission) as total 
        FROM activities 
        WHERE user_id = ? AND date >= date('now', '-7 days')
        GROUP BY date
        ORDER BY date
    """, (session["user_id"],)).fetchall()
    
    # Get category breakdown
    category_breakdown = conn.execute("""
        SELECT category, SUM(emission) as total, COUNT(*) as count
        FROM activities 
        WHERE user_id = ?
        GROUP BY category
    """, (session["user_id"],)).fetchall()
    
    conn.close()
    
    # Generate recommendation
    recommendation = ""
    if total_emission == 0:
        recommendation = "Start tracking your carbon footprint by adding activities!"
    elif total_emission < 2:
        recommendation = "Great job! Your carbon footprint is very low."
    elif total_emission < 5:
        recommendation = "Good! Your emissions are moderate. Keep it up!"
    elif total_emission < 10:
        recommendation = "Moderate emissions. Consider reducing car usage or meat consumption."
    else:
        recommendation = "High emissions detected. Try using public transport or reducing energy usage."
    
    return render_template(
        "dashboard.html",
        activities=activities,
        total_emission=round(total_emission, 4),
        weekly_data=weekly_data,
        category_breakdown=category_breakdown,
        recommendation=recommendation,
        is_authenticated=True,
        username=session.get("username", "User")
    )

@app.route("/add", methods=["POST"])
@login_required
def add_activity():
    category = request.form.get("category")
    activity_type = request.form.get("activity_type")
    amount = float(request.form.get("amount", 0))
    unit = request.form.get("unit")
    manual_date = request.form.get("manual_date")
    
    if not category or not activity_type or amount <= 0:
        flash("Please fill in all fields correctly", "error")
        return redirect("/dashboard")
    
    emission = calculate_emission(category, activity_type, amount, unit)
    
    # Use manual date if provided, otherwise use current date
    activity_date = manual_date if manual_date else datetime.now().strftime("%Y-%m-%d")
    
    conn = get_db()
    conn.execute("""
        INSERT INTO activities (user_id, category, activity_type, amount, unit, emission, date, manual_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (session["user_id"], category, activity_type, amount, unit, emission, activity_date, manual_date))
    conn.commit()
    conn.close()
    
    flash("Activity added successfully!", "success")
    return redirect("/dashboard")

@app.route("/delete/<int:activity_id>")
@login_required
def delete_activity(activity_id):
    conn = get_db()
    conn.execute("DELETE FROM activities WHERE id = ? AND user_id = ?", 
                (activity_id, session["user_id"]))
    conn.commit()
    conn.close()
    
    flash("Activity deleted", "success")
    return redirect("/dashboard")

@app.route("/insights")
@login_required
def insights():
    conn = get_db()
    
    # Get category breakdown
    category_data = conn.execute("""
        SELECT category, SUM(emission) as total, COUNT(*) as count
        FROM activities 
        WHERE user_id = ?
        GROUP BY category
        ORDER BY total DESC
    """, (session["user_id"],)).fetchall()
    
    # Get daily totals for last 30 days
    daily_data = conn.execute("""
        SELECT date, SUM(emission) as total
        FROM activities 
        WHERE user_id = ? AND date >= date('now', '-30 days')
        GROUP BY date
        ORDER BY date
    """, (session["user_id"],)).fetchall()
    
    # Get activity type breakdown
    type_data = conn.execute("""
        SELECT activity_type, SUM(emission) as total, COUNT(*) as count
        FROM activities 
        WHERE user_id = ?
        GROUP BY activity_type
        ORDER BY total DESC
    """, (session["user_id"],)).fetchall()
    
    conn.close()
    
    return render_template(
        "dashboard.html",
        category_data=category_data,
        daily_data=daily_data,
        type_data=type_data,
        is_authenticated=True,
        username=session.get("username", "User")
    )

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# Production deployment entry point
# Render provides PORT environment variable
if __name__ == "__main__":
    import os
    # Get port from environment variable (Render sets this), default to 5000
    # Run on all interfaces (0.0.0.0) for production access
    # debug=True enables auto-reload for local development
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=True
    )