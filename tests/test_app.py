"""Run with:  python -m unittest discover tests   (or: pytest)"""
import os
import re
import shutil
import sqlite3
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

TMP = tempfile.mkdtemp()
os.environ["DATABASE_PATH"] = os.path.join(TMP, "test.db")
os.environ.pop("DATABASE_URL", None)
os.environ.pop("ENVIRONMENT", None)
os.environ.pop("RENDER", None)

import app as app_module  # noqa: E402
from app import app, calculate_emission, today  # noqa: E402


def csrf(html):
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    return m.group(1) if m else ""


class Base(unittest.TestCase):
    def setUp(self):
        conn = sqlite3.connect(os.environ["DATABASE_PATH"])
        conn.execute("DELETE FROM activities")
        conn.execute("DELETE FROM users")
        conn.commit()
        conn.close()
        self.c = app.test_client()

    def token(self, path="/register"):
        return csrf(self.c.get(path).get_data(as_text=True))

    def signup(self, username="galvin", password="password123"):
        t = self.token("/register")
        self.c.post("/register", data={"username": username, "password": password,
                                       "confirm_password": password, "csrf_token": t})
        t = self.token("/login")
        return self.c.post("/login", data={"username": username, "password": password, "csrf_token": t})

    def add(self, **data):
        data.setdefault("csrf_token", self.token("/dashboard"))
        return self.c.post("/add", data=data)

    def rows(self):
        conn = sqlite3.connect(os.environ["DATABASE_PATH"])
        conn.row_factory = sqlite3.Row
        r = [dict(x) for x in conn.execute("SELECT * FROM activities ORDER BY id")]
        conn.close()
        return r


class TestCalculator(unittest.TestCase):
    def test_transport(self):
        self.assertEqual(calculate_emission("transport", "car_petrol", 10), (1.7, "km"))

    def test_energy_uses_power_and_grid(self):
        kg, unit = calculate_emission("energy", "ac", 2)
        self.assertAlmostEqual(kg, 2 * 1.5 * 0.72)
        self.assertEqual(unit, "hours")

    def test_electricity_kwh_unit(self):
        self.assertEqual(calculate_emission("energy", "electricity_kwh", 10)[1], "kWh")

    def test_food_servings(self):
        kg, unit = calculate_emission("food", "chicken", 2, "servings")
        self.assertAlmostEqual(kg, round(2 * 0.15 * 9.9, 4))
        self.assertEqual(unit, "servings")

    def test_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            calculate_emission("transport", "rocket", 1)
        with self.assertRaises(ValueError):
            calculate_emission("energy", "car_petrol", 1)  # item from another category
        with self.assertRaises(ValueError):
            calculate_emission("transport", "bus", 0)


class TestAuth(Base):
    def test_signup_login_logout(self):
        r = self.signup()
        self.assertEqual(r.status_code, 302)
        self.assertIn("/dashboard", r.headers["Location"])
        self.assertEqual(self.c.get("/dashboard").status_code, 200)
        t = self.token("/dashboard")
        self.c.post("/logout", data={"csrf_token": t})
        self.assertEqual(self.c.get("/dashboard").status_code, 302)

    def test_short_password_rejected(self):
        t = self.token()
        r = self.c.post("/register", data={"username": "abc", "password": "123", "csrf_token": t})
        self.assertEqual(r.status_code, 400)

    def test_duplicate_username(self):
        self.signup()
        c2 = app.test_client()
        t = csrf(c2.get("/register").get_data(as_text=True))
        r = c2.post("/register", data={"username": "galvin", "password": "password123",
                                       "confirm_password": "password123", "csrf_token": t})
        self.assertEqual(r.status_code, 400)
        self.assertIn("taken", r.get_data(as_text=True))

    def test_post_without_csrf_is_rejected(self):
        self.signup()
        r = self.c.post("/add", data={"category": "transport", "activity_type": "bus", "amount": "5"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.rows(), [])

    def test_open_redirect_blocked(self):
        t = self.token()
        self.c.post("/register", data={"username": "zed", "password": "password123",
                                       "confirm_password": "password123", "csrf_token": t})
        t = self.token("/login")
        r = self.c.post("/login?next=//evil.com", data={"username": "zed", "password": "password123", "csrf_token": t})
        self.assertNotIn("evil.com", r.headers["Location"])


class TestActivities(Base):
    def setUp(self):
        super().setUp()
        self.signup()

    def test_add_saves_category_unit_and_date(self):
        self.add(category="transport", activity_type="bus", amount="10")
        r = self.rows()[0]
        self.assertEqual(r["category"], "transport")
        self.assertEqual(r["activity_type"], "bus")
        self.assertEqual(r["unit"], "km")
        self.assertEqual(r["date"], today().isoformat())
        self.assertAlmostEqual(r["emission"], 0.8)

    def test_add_with_past_date_and_servings(self):
        d = (today() - timedelta(days=3)).isoformat()
        self.add(category="food", activity_type="rice", amount="2", mode="servings", date=d)
        r = self.rows()[0]
        self.assertEqual(r["date"], d)
        self.assertEqual(r["unit"], "servings")

    def test_future_date_rejected(self):
        d = (today() + timedelta(days=1)).isoformat()
        self.add(category="transport", activity_type="bus", amount="10", date=d)
        self.assertEqual(self.rows(), [])

    def test_bad_amount_rejected(self):
        self.add(category="transport", activity_type="bus", amount="abc")
        self.add(category="transport", activity_type="bus", amount="-4")
        self.assertEqual(self.rows(), [])

    def test_json_api_still_works(self):
        t = self.token("/dashboard")
        r = self.c.post("/add", json={"category": "waste", "type": "plastic", "amount": 1},
                        headers={"X-CSRF-Token": t})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["ok"])

    def test_delete_is_post_and_scoped_to_user(self):
        self.add(category="transport", activity_type="bus", amount="10")
        aid = self.rows()[0]["id"]
        self.assertEqual(self.c.get(f"/delete/{aid}").status_code, 405)

        other = app.test_client()
        t = csrf(other.get("/register").get_data(as_text=True))
        other.post("/register", data={"username": "other", "password": "password123",
                                      "confirm_password": "password123", "csrf_token": t})
        t = csrf(other.get("/login").get_data(as_text=True))
        other.post("/login", data={"username": "other", "password": "password123", "csrf_token": t})
        t = csrf(other.get("/dashboard").get_data(as_text=True))
        other.post(f"/delete/{aid}", data={"csrf_token": t})
        self.assertEqual(len(self.rows()), 1)

        self.c.post(f"/delete/{aid}", data={"csrf_token": self.token("/dashboard")})
        self.assertEqual(self.rows(), [])

    def test_dashboard_stats_and_goal(self):
        self.add(category="transport", activity_type="car_petrol", amount="100")  # 17 kg
        self.add(category="energy", activity_type="ac", amount="1")               # 1.08 kg
        self.c.post("/goal", data={"monthly_goal": "100", "csrf_token": self.token("/dashboard")})
        with app.test_request_context():
            from flask import session
            uid = self.rows()[0]["user_id"]
            session["user_id"] = uid
            stats = app_module.build_stats(uid)
        self.assertAlmostEqual(stats["week_total"], 18.08, places=2)
        self.assertAlmostEqual(stats["by_cat"]["transport"], 17)
        self.assertEqual(stats["goal"], 100)
        self.assertEqual(stats["goal_pct"], 18)
        self.assertEqual(len(stats["chart"]["values"]), 30)
        self.assertAlmostEqual(stats["chart"]["values"][-1], 18.08, places=2)
        self.assertIn("Transport", stats["tips"][0])
        html = self.c.get("/dashboard").get_data(as_text=True)
        self.assertIn("18% of your 100 kg goal", html)

    def test_activities_page_filter_and_csv(self):
        self.add(category="transport", activity_type="bus", amount="10")
        self.add(category="food", activity_type="beef", amount="0.2")
        html = self.c.get("/activities?category=food").get_data(as_text=True)
        self.assertIn("Beef", html)
        self.assertNotIn(">Bus<", html)
        csv = self.c.get("/export.csv")
        self.assertEqual(csv.mimetype, "text/csv")
        lines = csv.get_data(as_text=True).strip().splitlines()
        self.assertEqual(lines[0], "date,category,activity,amount,unit,kg_co2e")
        self.assertEqual(len(lines), 3)

    def test_insights_redirects(self):
        self.assertEqual(self.c.get("/insights").status_code, 302)


class TestMigration(unittest.TestCase):
    def test_old_rows_are_fixed(self):
        path = Path(TMP) / "old.db"
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, "
                     "password TEXT NOT NULL, created_at TEXT)")
        conn.execute("CREATE TABLE activities (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, "
                     "category TEXT NOT NULL, activity_type TEXT NOT NULL, amount REAL NOT NULL, unit TEXT NOT NULL, "
                     "emission REAL NOT NULL, date TEXT NOT NULL, manual_date TEXT)")
        conn.execute("INSERT INTO users (username, password) VALUES ('u', 'x')")
        conn.execute("INSERT INTO activities (user_id, category, activity_type, amount, unit, emission, date) "
                     "VALUES (1, 'car_petrol', 'car_petrol', 3, 'units', 0.57, '2026-04-27T16:15:43.372Z')")
        conn.commit()
        conn.close()

        old = os.environ["DATABASE_PATH"]
        os.environ["DATABASE_PATH"] = str(path)
        try:
            app_module.init_db()
        finally:
            os.environ["DATABASE_PATH"] = old

        conn = sqlite3.connect(path)
        row = conn.execute("SELECT category, unit, date, emission FROM activities").fetchone()
        cols = [r[1] for r in conn.execute("PRAGMA table_info(users)")]
        conn.close()
        self.assertEqual(row, ("transport", "km", "2026-04-27", 0.51))
        self.assertIn("monthly_goal", cols)


def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
