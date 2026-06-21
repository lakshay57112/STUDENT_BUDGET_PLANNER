"""
============================================================
 Student Budget Planner - Flask Web Application
============================================================
 A web-based budget tracker for students.

 Tech stack (from proposal):
   - Backend:   Python Flask
   - Database:  SQLite
   - Frontend:  HTML5 / CSS3 / Bootstrap 5 / JavaScript
   - Charts:    Chart.js

 Features (Functional Requirements):
   FR-01  User Registration
   FR-02  User Login
   FR-03  Budget Creation (per category, per month)
   FR-04  Expense Recording
   FR-05  Expense Modification
   FR-06  Expense Deletion
   FR-07  Dashboard View (real-time summary + charts)
   FR-08  Report Generation (category breakdown)
   FR-09  User Logout

 HOW TO RUN:
   1. pip install -r requirements.txt
   2. python app.py
   3. Open http://127.0.0.1:5000 in your browser
============================================================
"""

import sqlite3
import os
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify, g
)
from werkzeug.security import generate_password_hash, check_password_hash

# ─────────────────────────────────────────────
#  App Configuration
# ─────────────────────────────────────────────
app = Flask(__name__)

# Secret key is used to sign session cookies (keeps logins secure).
# In a real deployment, load this from an environment variable.
app.secret_key = "change-this-to-a-random-secret-key-in-production"

# Path to the SQLite database file (created automatically on first run)
DB_PATH = os.path.join(os.path.dirname(__file__), "budget_planner.db")


# ─────────────────────────────────────────────
#  Categories (fixed list, like the mobile app)
# ─────────────────────────────────────────────
# Each category has a color so charts and labels stay consistent.
EXPENSE_CATEGORIES = [
    {"name": "Food",          "color": "#FF6B6B"},
    {"name": "Transport",     "color": "#4ECDC4"},
    {"name": "Shopping",      "color": "#FFBE0B"},
    {"name": "Entertainment", "color": "#FF006E"},
    {"name": "Books",         "color": "#8338EC"},
    {"name": "Tuition",       "color": "#3A86FF"},
    {"name": "Rent",          "color": "#FB5607"},
    {"name": "Health",        "color": "#E63946"},
    {"name": "Utilities",     "color": "#06D6A0"},
    {"name": "Other",         "color": "#8D99AE"},
]

INCOME_CATEGORIES = [
    {"name": "Allowance",     "color": "#2EC4B6"},
    {"name": "Part-time Job", "color": "#3A86FF"},
    {"name": "Freelance",     "color": "#8338EC"},
    {"name": "Scholarship",   "color": "#FFBE0B"},
    {"name": "Gift",          "color": "#FF006E"},
    {"name": "Other Income",  "color": "#06D6A0"},
]


def category_color(name):
    """Return the color hex for a category name (used in templates)."""
    for c in EXPENSE_CATEGORIES + INCOME_CATEGORIES:
        if c["name"] == name:
            return c["color"]
    return "#8D99AE"


# ─────────────────────────────────────────────
#  Database Helpers
# ─────────────────────────────────────────────
def get_db():
    """
    Open a database connection for the current request.
    Reuses the same connection if one already exists (stored in 'g').
    """
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        # Rows behave like dictionaries: row["column_name"]
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    """Close the database connection when the request ends."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """
    Create the database tables if they don't exist yet.
    Runs once when the app starts.
    """
    db = sqlite3.connect(DB_PATH)
    db.executescript("""
        -- Users table (FR-01, FR-02)
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name     TEXT    NOT NULL,
            email         TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            created_at    TEXT    NOT NULL
        );

        -- Budgets table (FR-03): one limit per category, per month
        CREATE TABLE IF NOT EXISTS budgets (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER NOT NULL,
            category  TEXT    NOT NULL,
            amount    REAL    NOT NULL,
            month     INTEGER NOT NULL,
            year      INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE (user_id, category, month, year)
        );

        -- Expenses table (FR-04, FR-05, FR-06)
        -- 'type' is either 'income' or 'expense'
        CREATE TABLE IF NOT EXISTS expenses (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER NOT NULL,
            title     TEXT    NOT NULL,
            amount    REAL    NOT NULL,
            category  TEXT    NOT NULL,
            type      TEXT    NOT NULL,
            date      TEXT    NOT NULL,
            note      TEXT    DEFAULT '',
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
    """)
    db.commit()
    db.close()


# ─────────────────────────────────────────────
#  Authentication Helper
# ─────────────────────────────────────────────
def login_required(view):
    """
    Decorator that blocks access to a page unless the user is logged in.
    Add @login_required above any route that needs protection.
    """
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped_view


def current_month_year():
    """Read ?month= and ?year= from the URL, default to today."""
    now = datetime.now()
    try:
        month = int(request.args.get("month", now.month))
        year = int(request.args.get("year", now.year))
    except (ValueError, TypeError):
        month, year = now.month, now.year
    # Keep month in valid range
    if month < 1 or month > 12:
        month = now.month
    return month, year


# ─────────────────────────────────────────────
#  Authentication Routes (FR-01, FR-02, FR-09)
# ─────────────────────────────────────────────
@app.route("/")
def index():
    """Send logged-in users to the dashboard, others to login."""
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    """FR-01 — Create a new user account."""
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        # ── Validation ──
        if not full_name or not email or not password:
            flash("All fields are required.", "danger")
            return render_template("register.html")

        if password != confirm:
            flash("Passwords do not match.", "danger")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return render_template("register.html")

        db = get_db()
        existing = db.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()

        if existing:
            flash("An account with that email already exists.", "danger")
            return render_template("register.html")

        # ── Store the user with a HASHED password (NFR-02 security) ──
        db.execute(
            "INSERT INTO users (full_name, email, password_hash, created_at) "
            "VALUES (?, ?, ?, ?)",
            (full_name, email,
             generate_password_hash(password),
             datetime.now().isoformat()),
        )
        db.commit()

        flash("Account created! You can now log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """FR-02 — Authenticate an existing user."""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()

        # Check the password against the stored hash
        if user and check_password_hash(user["password_hash"], password):
            # Save the user's identity in the session (logs them in)
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["full_name"]
            return redirect(url_for("dashboard"))

        flash("Incorrect email or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    """FR-09 — End the user's session."""
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


# ─────────────────────────────────────────────
#  Dashboard (FR-07)
# ─────────────────────────────────────────────
@app.route("/dashboard")
@login_required
def dashboard():
    """Show the real-time financial overview for the selected month."""
    db = get_db()
    uid = session["user_id"]
    month, year = current_month_year()

    # All transactions for this month
    txns = db.execute(
        "SELECT * FROM expenses "
        "WHERE user_id = ? AND CAST(strftime('%m', date) AS INTEGER) = ? "
        "AND CAST(strftime('%Y', date) AS INTEGER) = ? "
        "ORDER BY date DESC",
        (uid, month, year),
    ).fetchall()

    # Calculate totals
    total_income = sum(t["amount"] for t in txns if t["type"] == "income")
    total_expense = sum(t["amount"] for t in txns if t["type"] == "expense")
    balance = total_income - total_expense

    # Total budget for the month (sum of all category budgets)
    budgets = db.execute(
        "SELECT * FROM budgets WHERE user_id = ? AND month = ? AND year = ?",
        (uid, month, year),
    ).fetchall()
    total_budget = sum(b["amount"] for b in budgets)

    # Over-budget categories (spent more than the limit)
    over_budget = []
    for b in budgets:
        spent = sum(
            t["amount"] for t in txns
            if t["type"] == "expense" and t["category"] == b["category"]
        )
        if spent > b["amount"]:
            over_budget.append(b["category"])

    return render_template(
        "dashboard.html",
        transactions=txns[:6],          # only the 6 most recent
        total_income=total_income,
        total_expense=total_expense,
        balance=balance,
        total_budget=total_budget,
        over_budget=over_budget,
        month=month,
        year=year,
        month_name=datetime(year, month, 1).strftime("%B %Y"),
        category_color=category_color,
    )


# ─────────────────────────────────────────────
#  Expenses (FR-04, FR-05, FR-06)
# ─────────────────────────────────────────────
@app.route("/expenses")
@login_required
def expenses():
    """List all transactions for the month, with a search filter."""
    db = get_db()
    uid = session["user_id"]
    month, year = current_month_year()
    search = request.args.get("search", "").strip().lower()

    txns = db.execute(
        "SELECT * FROM expenses "
        "WHERE user_id = ? AND CAST(strftime('%m', date) AS INTEGER) = ? "
        "AND CAST(strftime('%Y', date) AS INTEGER) = ? "
        "ORDER BY date DESC",
        (uid, month, year),
    ).fetchall()

    # Apply search filter (by title or category)
    if search:
        txns = [
            t for t in txns
            if search in t["title"].lower() or search in t["category"].lower()
        ]

    return render_template(
        "expenses.html",
        transactions=txns,
        expense_categories=EXPENSE_CATEGORIES,
        income_categories=INCOME_CATEGORIES,
        month=month,
        year=year,
        month_name=datetime(year, month, 1).strftime("%B %Y"),
        search=search,
        today=datetime.now().strftime("%Y-%m-%d"),
        category_color=category_color,
    )


@app.route("/expenses/add", methods=["POST"])
@login_required
def add_expense():
    """FR-04 — Add a new income or expense entry."""
    db = get_db()
    uid = session["user_id"]

    title = request.form.get("title", "").strip()
    category = request.form.get("category", "").strip()
    txn_type = request.form.get("type", "expense")
    date = request.form.get("date", datetime.now().strftime("%Y-%m-%d"))
    note = request.form.get("note", "").strip()

    # Validate the amount
    try:
        amount = float(request.form.get("amount", 0))
    except ValueError:
        amount = 0

    if not title or amount <= 0 or not category:
        flash("Please enter a title, a valid amount, and a category.", "danger")
        return redirect(url_for("expenses"))

    db.execute(
        "INSERT INTO expenses (user_id, title, amount, category, type, date, note) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (uid, title, amount, category, txn_type, date, note),
    )
    db.commit()
    flash(f"{'Income' if txn_type == 'income' else 'Expense'} added.", "success")
    return redirect(url_for("expenses", month=int(date[5:7]), year=int(date[:4])))


@app.route("/expenses/edit/<int:expense_id>", methods=["POST"])
@login_required
def edit_expense(expense_id):
    """FR-05 — Update an existing transaction."""
    db = get_db()
    uid = session["user_id"]

    title = request.form.get("title", "").strip()
    category = request.form.get("category", "").strip()
    txn_type = request.form.get("type", "expense")
    date = request.form.get("date", datetime.now().strftime("%Y-%m-%d"))
    note = request.form.get("note", "").strip()

    try:
        amount = float(request.form.get("amount", 0))
    except ValueError:
        amount = 0

    if not title or amount <= 0 or not category:
        flash("Please enter a title, a valid amount, and a category.", "danger")
        return redirect(url_for("expenses"))

    # The WHERE clause checks user_id so users can only edit their own data
    db.execute(
        "UPDATE expenses SET title = ?, amount = ?, category = ?, "
        "type = ?, date = ?, note = ? WHERE id = ? AND user_id = ?",
        (title, amount, category, txn_type, date, note, expense_id, uid),
    )
    db.commit()
    flash("Transaction updated.", "success")
    return redirect(url_for("expenses"))


@app.route("/expenses/delete/<int:expense_id>", methods=["POST"])
@login_required
def delete_expense(expense_id):
    """FR-06 — Permanently delete a transaction."""
    db = get_db()
    uid = session["user_id"]
    db.execute(
        "DELETE FROM expenses WHERE id = ? AND user_id = ?",
        (expense_id, uid),
    )
    db.commit()
    flash("Transaction deleted.", "success")
    return redirect(url_for("expenses"))


# ─────────────────────────────────────────────
#  Budgets (FR-03)
# ─────────────────────────────────────────────
@app.route("/budget")
@login_required
def budget():
    """Show budget limits and how much has been spent in each category."""
    db = get_db()
    uid = session["user_id"]
    month, year = current_month_year()

    budgets = db.execute(
        "SELECT * FROM budgets WHERE user_id = ? AND month = ? AND year = ? "
        "ORDER BY category",
        (uid, month, year),
    ).fetchall()

    # For each budget, compute how much was spent in that category this month
    budget_data = []
    for b in budgets:
        spent = db.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses "
            "WHERE user_id = ? AND category = ? AND type = 'expense' "
            "AND CAST(strftime('%m', date) AS INTEGER) = ? "
            "AND CAST(strftime('%Y', date) AS INTEGER) = ?",
            (uid, b["category"], month, year),
        ).fetchone()["total"]

        percent = (spent / b["amount"] * 100) if b["amount"] > 0 else 0
        budget_data.append({
            "id": b["id"],
            "category": b["category"],
            "limit": b["amount"],
            "spent": spent,
            "remaining": b["amount"] - spent,
            "percent": min(percent, 100),
            "over": spent > b["amount"],
            "color": category_color(b["category"]),
        })

    return render_template(
        "budget.html",
        budget_data=budget_data,
        expense_categories=EXPENSE_CATEGORIES,
        month=month,
        year=year,
        month_name=datetime(year, month, 1).strftime("%B %Y"),
    )


@app.route("/budget/set", methods=["POST"])
@login_required
def set_budget():
    """FR-03 — Create or update a budget limit for a category."""
    db = get_db()
    uid = session["user_id"]
    month, year = current_month_year()

    category = request.form.get("category", "").strip()
    try:
        amount = float(request.form.get("amount", 0))
    except ValueError:
        amount = 0

    if not category or amount <= 0:
        flash("Please choose a category and enter a valid limit.", "danger")
        return redirect(url_for("budget", month=month, year=year))

    # INSERT, or UPDATE if a budget for this category+month already exists
    db.execute(
        "INSERT INTO budgets (user_id, category, amount, month, year) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(user_id, category, month, year) "
        "DO UPDATE SET amount = excluded.amount",
        (uid, category, amount, month, year),
    )
    db.commit()
    flash("Budget limit saved.", "success")
    return redirect(url_for("budget", month=month, year=year))


@app.route("/budget/delete/<int:budget_id>", methods=["POST"])
@login_required
def delete_budget(budget_id):
    """Remove a budget limit."""
    db = get_db()
    uid = session["user_id"]
    db.execute(
        "DELETE FROM budgets WHERE id = ? AND user_id = ?",
        (budget_id, uid),
    )
    db.commit()
    flash("Budget removed.", "success")
    return redirect(url_for("budget"))


# ─────────────────────────────────────────────
#  Reports (FR-08)
# ─────────────────────────────────────────────
@app.route("/reports")
@login_required
def reports():
    """Show category-based spending analysis for the month."""
    db = get_db()
    uid = session["user_id"]
    month, year = current_month_year()

    rows = db.execute(
        "SELECT category, SUM(amount) AS total FROM expenses "
        "WHERE user_id = ? AND type = 'expense' "
        "AND CAST(strftime('%m', date) AS INTEGER) = ? "
        "AND CAST(strftime('%Y', date) AS INTEGER) = ? "
        "GROUP BY category ORDER BY total DESC",
        (uid, month, year),
    ).fetchall()

    total = sum(r["total"] for r in rows)
    breakdown = [{
        "category": r["category"],
        "total": r["total"],
        "percent": (r["total"] / total * 100) if total > 0 else 0,
        "color": category_color(r["category"]),
    } for r in rows]

    return render_template(
        "reports.html",
        breakdown=breakdown,
        total=total,
        month=month,
        year=year,
        month_name=datetime(year, month, 1).strftime("%B %Y"),
    )


# ─────────────────────────────────────────────
#  Chart Data API (used by Chart.js on the frontend)
# ─────────────────────────────────────────────
@app.route("/api/chart-data")
@login_required
def chart_data():
    """
    Return JSON data for the dashboard and report charts.
    The frontend JavaScript fetches this and draws the charts.
    """
    db = get_db()
    uid = session["user_id"]
    month, year = current_month_year()

    # ── Weekly spending (last 7 days) for the bar chart ──
    txns = db.execute(
        "SELECT date, amount, type FROM expenses WHERE user_id = ?",
        (uid,),
    ).fetchall()

    today = datetime.now()
    week_labels, week_values = [], []
    for i in range(6, -1, -1):
        day = today.fromordinal(today.toordinal() - i)
        label = day.strftime("%m/%d")
        total = sum(
            t["amount"] for t in txns
            if t["type"] == "expense" and t["date"][:10] == day.strftime("%Y-%m-%d")
        )
        week_labels.append(label)
        week_values.append(round(total, 2))

    # ── Category breakdown for the pie/donut chart ──
    rows = db.execute(
        "SELECT category, SUM(amount) AS total FROM expenses "
        "WHERE user_id = ? AND type = 'expense' "
        "AND CAST(strftime('%m', date) AS INTEGER) = ? "
        "AND CAST(strftime('%Y', date) AS INTEGER) = ? "
        "GROUP BY category",
        (uid, month, year),
    ).fetchall()

    cat_labels = [r["category"] for r in rows]
    cat_values = [round(r["total"], 2) for r in rows]
    cat_colors = [category_color(r["category"]) for r in rows]

    return jsonify({
        "week": {"labels": week_labels, "values": week_values},
        "categories": {
            "labels": cat_labels,
            "values": cat_values,
            "colors": cat_colors,
        },
    })


# ─────────────────────────────────────────────
#  Start the App
# ─────────────────────────────────────────────
import os

if __name__ == "__main__":
    init_db()  # Make sure tables exist before serving
    print("=" * 50)
    print(" Student Budget Planner is running!")
    print("=" * 50)

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
